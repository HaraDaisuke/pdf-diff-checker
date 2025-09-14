from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageChops
import io
import asyncio
import cv2
import numpy as np
import base64
import json

app = FastAPI()

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],  # Vue.js開発サーバーのオリジン
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def convert_pdf_page_to_image(pdf_bytes: bytes, page_num: int):
    """PDFの指定されたページをPillow画像オブジェクトに変換する"""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_num >= doc.page_count:
            raise HTTPException(status_code=400, detail=f"無効なページ番号: {page_num}")
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes())).convert("RGB")
        doc.close()
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ページ {page_num + 1} の画像化に失敗しました: {e}")

def run_comparison(img1: Image.Image, img2: Image.Image, threshold: int, box_size: int, dilation_iterations: int):
    """2つの画像を比較し、差分画像と部品リストを返す共通関数"""
    # --- グローバル位置合わせ ---
    img1_cv = np.array(img1)
    img2_cv = np.array(img2)
    img1_gray = cv2.cvtColor(img1_cv, cv2.COLOR_RGB2GRAY)
    img2_gray = cv2.cvtColor(img2_cv, cv2.COLOR_RGB2GRAY)
    
    shift, _ = cv2.phaseCorrelate(np.float32(img1_gray), np.float32(img2_gray))
    dx, dy = shift
    shift_x, shift_y = -dx, -dy

    rows, cols = img1_gray.shape
    M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    aligned_img2_cv = cv2.warpAffine(img2_cv, M, (cols, rows))
    aligned_img2 = Image.fromarray(aligned_img2_cv)

    # --- 差分検出 ---
    mask = Image.new('L', img1.size, 255)
    mask_draw = ImageDraw.Draw(mask)
    if shift_y > 0: mask_draw.rectangle([0, 0, cols, int(shift_y)], fill=0)
    elif shift_y < 0: mask_draw.rectangle([0, rows - int(abs(shift_y)), cols, rows], fill=0)
    if shift_x > 0: mask_draw.rectangle([0, 0, int(shift_x), rows], fill=0)
    elif shift_x < 0: mask_draw.rectangle([cols - int(abs(shift_x)), 0, cols, rows], fill=0)

    pixels1 = img1.load()
    pixels2 = aligned_img2.load()
    mask_pixels = mask.load()
    
    diff_areas = []
    for y in range(rows):
        for x in range(cols):
            if mask_pixels[x, y] == 0: continue
            if color_difference(p1=pixels1[x, y], p2=pixels2[x, y]) > threshold:
                diff_areas.append((x, y))

    output_img = img1.copy()
    if diff_areas:
        draw = ImageDraw.Draw(output_img)
        for x, y in diff_areas:
            draw.rectangle([x - box_size, y - box_size, x + box_size, y + box_size], outline="red", width=1)

    # --- 部品検出 ---
    aligned_img2_gray = cv2.cvtColor(aligned_img2_cv, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(aligned_img2_gray, 240, 255, cv2.THRESH_BINARY_INV)
    
    if dilation_iterations > 0:
        kernel = np.ones((3,3), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=dilation_iterations)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    rectangles = []
    min_area = 50
    for cnt in contours:
        if cv2.contourArea(cnt) > min_area:
            x, y, w, h = cv2.boundingRect(cnt)
            rectangles.append({"x": x, "y": y, "w": w, "h": h})

    # --- 画像のBase64エンコード ---
    def to_base64(img):
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    img_diff_base64 = to_base64(output_img)
    img_before_base64 = to_base64(img1)
    img_after_base64 = to_base64(aligned_img2)

    return {
        "image_diff": f"data:image/png;base64,{img_diff_base64}",
        "image_before": f"data:image/png;base64,{img_before_base64}",
        "image_after": f"data:image/png;base64,{img_after_base64}",
        "rectangles": rectangles,
    }

def color_difference(p1, p2):
    """2つのピクセルの色差を計算する"""
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) + abs(p1[2] - p2[2])

@app.post("/api/diff")
async def diff_endpoint(file1: UploadFile = File(...), file2: UploadFile = File(...), threshold: int = Form(30), box_size: int = Form(5), dilation_iterations: int = Form(0)):
    pdf1_bytes = await file1.read()
    pdf2_bytes = await file2.read()

    try:
        doc1 = fitz.open(stream=pdf1_bytes, filetype="pdf")
        doc2 = fitz.open(stream=pdf2_bytes, filetype="pdf")
        
        num_pages = min(doc1.page_count, doc2.page_count)
        doc1.close()
        doc2.close()

        results = []

        for i in range(num_pages):
            img1 = await convert_pdf_page_to_image(pdf1_bytes, i)
            img2 = await convert_pdf_page_to_image(pdf2_bytes, i)
            
            comparison_result = run_comparison(img1, img2, threshold, box_size, dilation_iterations)
            comparison_result["page_number"] = i + 1
            results.append(comparison_result)
        
        return JSONResponse(content={"results": results})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF処理中にエラーが発生しました: {e}")

@app.post("/api/diff-images")
async def diff_images_endpoint(file1: UploadFile = File(...), file2: UploadFile = File(...), threshold: int = Form(30), box_size: int = Form(5), dilation_iterations: int = Form(0)):
    try:
        img1_bytes = await file1.read()
        img2_bytes = await file2.read()

        img1 = Image.open(io.BytesIO(img1_bytes)).convert("RGBA")
        img2 = Image.open(io.BytesIO(img2_bytes)).convert("RGBA")

        if img1.size != img2.size:
            max_width = max(img1.width, img2.width)
            max_height = max(img1.height, img2.height)
            new_img1 = Image.new('RGBA', (max_width, max_height), (255, 255, 255, 255))
            new_img2 = Image.new('RGBA', (max_width, max_height), (255, 255, 255, 255))
            paste_pos1 = ((max_width - img1.width) // 2, (max_height - img1.height) // 2)
            paste_pos2 = ((max_width - img2.width) // 2, (max_height - img2.height) // 2)
            new_img1.paste(img1, paste_pos1, img1)
            new_img2.paste(img2, paste_pos2, img2)
            img1 = new_img1
            img2 = new_img2

        img1 = img1.convert("RGB")
        img2 = img2.convert("RGB")

        result = run_comparison(img1, img2, threshold, box_size, dilation_iterations)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"画像の処理中にエラーが発生しました: {e}")

@app.post("/api/align-part")
async def align_part_endpoint(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    threshold: int = Form(30),
    box_size: int = Form(5),
    dilation_iterations: int = Form(0),
    selected_rect: str = Form(...)
):
    pdf1_bytes = await file1.read()
    pdf2_bytes = await file2.read()
    # Note: This endpoint assumes page 0 for now.
    img1 = await convert_pdf_page_to_image(pdf1_bytes, 0)
    img2 = await convert_pdf_page_to_image(pdf2_bytes, 0)

    img1_cv = np.array(img1)
    img2_cv = np.array(img2)
    img1_gray = cv2.cvtColor(img1_cv, cv2.COLOR_RGB2GRAY)
    img2_gray = cv2.cvtColor(img2_cv, cv2.COLOR_RGB2GRAY)
    
    shift, _ = cv2.phaseCorrelate(np.float32(img1_gray), np.float32(img2_gray))
    dx, dy = shift
    shift_x, shift_y = -dx, -dy

    rows, cols = img1_gray.shape
    M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    aligned_img2_cv = cv2.warpAffine(img2_cv, M, (cols, rows))
    aligned_img2 = Image.fromarray(aligned_img2_cv)

    rect = json.loads(selected_rect)

    part_template = aligned_img2.crop((rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h']))
    template_cv = np.array(part_template)
    
    aligned_img1_cv = np.array(img1)
    res = cv2.matchTemplate(aligned_img1_cv, template_cv, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    new_x, new_y = max_loc

    modified_aligned_img2 = aligned_img2.copy()
    ImageDraw.Draw(modified_aligned_img2).rectangle(
        (rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h']),
        fill=(255, 255, 255)
    )
    modified_aligned_img2.paste(part_template, (new_x, new_y))

    result = run_comparison(img1, modified_aligned_img2, threshold, box_size, dilation_iterations)
    return JSONResponse(content=result)


def _crop_image(image_cv, points_str: str):
    points = json.loads(points_str)
    if not points:
        return None

    rows, cols = image_cv.shape[:2]
    pts = np.array([[p['x'], p['y']] for p in points], dtype=np.int32)
    x, y, w, h = cv2.boundingRect(pts)

    x = max(0, x)
    y = max(0, y)
    w = min(w, cols - x)
    h = min(h, rows - y)

    pts_roi = pts - np.array([x, y])

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts_roi], 255)

    roi = image_cv[y:y+h, x:x+w]
    roi_rgba = cv2.cvtColor(roi, cv2.COLOR_RGB2RGBA)
    roi_rgba[:, :, 3] = mask

    return Image.fromarray(roi_rgba)

@app.post("/api/crop-by-selection")
async def crop_by_selection_endpoint(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    page_num1: int = Form(...),
    page_num2: int = Form(...),
    selection_points: str = Form(...)
):
    try:
        pdf1_bytes = await file1.read()
        pdf2_bytes = await file2.read()
        img1 = await convert_pdf_page_to_image(pdf1_bytes, page_num1)
        img2 = await convert_pdf_page_to_image(pdf2_bytes, page_num2)

        img1_cv = np.array(img1)
        img2_cv = np.array(img2)

        # Only perform global alignment if the pages are the same
        if page_num1 == page_num2:
            img1_gray = cv2.cvtColor(img1_cv, cv2.COLOR_RGB2GRAY)
            img2_gray = cv2.cvtColor(img2_cv, cv2.COLOR_RGB2GRAY)
            shift, _ = cv2.phaseCorrelate(np.float32(img1_gray), np.float32(img2_gray))
            dx, dy = shift
            shift_x, shift_y = -dx, -dy
            rows, cols = img1_gray.shape
            M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
            aligned_img2_cv = cv2.warpAffine(img2_cv, M, (cols, rows))
            aligned_img1_cv = img1_cv
        else:
            aligned_img1_cv = img1_cv
            aligned_img2_cv = img2_cv

        cropped_img1 = _crop_image(aligned_img1_cv, selection_points)
        cropped_img2 = _crop_image(aligned_img2_cv, selection_points)

        if cropped_img1 is None or cropped_img2 is None:
            raise HTTPException(status_code=400, detail="選択範囲の点がありません")

        def to_base64(img):
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return base64.b64encode(buf.getvalue()).decode('utf-8')

        return JSONResponse(content={
            "cropped_before": f"data:image/png;base64,{to_base64(cropped_img1)}",
            "cropped_after": f"data:image/png;base64,{to_base64(cropped_img2)}",
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"処理中にエラーが発生しました: {e}")

@app.post("/api/crop-by-independent-selections")
async def crop_by_independent_selections_endpoint(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    page_num1: int = Form(...),
    page_num2: int = Form(...),
    selection_points_before: str = Form(...),
    selection_points_after: str = Form(...)
):
    try:
        pdf1_bytes = await file1.read()
        pdf2_bytes = await file2.read()
        img1 = await convert_pdf_page_to_image(pdf1_bytes, page_num1)
        img2 = await convert_pdf_page_to_image(pdf2_bytes, page_num2)

        # Convert to CV format WITHOUT global alignment for independent selections
        aligned_img1_cv = np.array(img1)
        aligned_img2_cv = np.array(img2)

        cropped_img1 = _crop_image(aligned_img1_cv, selection_points_before)
        cropped_img2 = _crop_image(aligned_img2_cv, selection_points_after)

        if cropped_img1 is None or cropped_img2 is None:
            raise HTTPException(status_code=400, detail="選択範囲の点がありません")

        def to_base64(img):
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return base64.b64encode(buf.getvalue()).decode('utf-8')

        return JSONResponse(content={
            "cropped_before": f"data:image/png;base64,{to_base64(cropped_img1)}",
            "cropped_after": f"data:image/png;base64,{to_base64(cropped_img2)}",
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"処理中にエラーが発生しました: {e}")

@app.post("/api/pdf-thumbnails")
async def pdf_thumbnails_endpoint(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        thumbnails = []
        for i in range(doc.page_count):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=72)
            img = Image.open(io.BytesIO(pix.tobytes()))
            
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            base64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
            thumbnails.append(f"data:image/png;base64,{base64_str}")
            
        doc.close()
        return JSONResponse(content={"thumbnails": thumbnails})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"サムネイル生成中にエラーが発生しました: {e}")

@app.post("/api/get-pdf-pages")
async def get_pdf_pages_endpoint(
    file1: UploadFile = File(...), 
    file2: UploadFile = File(...),
    page_num1: int = Form(...),
    page_num2: int = Form(...)
):
    try:
        pdf1_bytes = await file1.read()
        pdf2_bytes = await file2.read()

        img1 = await convert_pdf_page_to_image(pdf1_bytes, page_num1)
        img2 = await convert_pdf_page_to_image(pdf2_bytes, page_num2)

        def to_base64(img):
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return base64.b64encode(buf.getvalue()).decode('utf-8')

        img1_base64 = to_base64(img1)
        img2_base64 = to_base64(img2)

        return JSONResponse(content={
            "image_before": f"data:image/png;base64,{img1_base64}",
            "image_after": f"data:image/png;base64,{img2_base64}",
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ページ画像の取得中にエラーが発生しました: {e}")

@app.get("/")
def read_root():
    return {"message": "PDF Diff Checker API"}
