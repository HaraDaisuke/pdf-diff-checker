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

async def convert_pdf_to_image(pdf_file: UploadFile):
    """PDFをPillow画像オブジェクトに変換する"""
    try:
        pdf_bytes = await pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes())).convert("RGB")
        doc.close()
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDFの画像化に失敗しました: {e}")

def color_difference(p1, p2):
    """2つのピクセルの色差を計算する"""
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) + abs(p1[2] - p2[2])

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
            if color_difference(pixels1[x, y], pixels2[x, y]) > threshold:
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

    buf = io.BytesIO()
    output_img.save(buf, format='PNG')
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return {
        "image": "data:image/png;base64," + img_base64,
        "rectangles": rectangles,
        "aligned_img2_base64": base64.b64encode(io.BytesIO(aligned_img2_cv.tobytes()).getvalue()).decode('utf-8') # Return aligned img2 for subsequent part alignment
    }

@app.post("/api/diff")
async def diff_endpoint(file1: UploadFile = File(...), file2: UploadFile = File(...), threshold: int = Form(30), box_size: int = Form(5), dilation_iterations: int = Form(0)):
    img1 = await convert_pdf_to_image(file1)
    img2 = await convert_pdf_to_image(file2)
    result = run_comparison(img1, img2, threshold, box_size, dilation_iterations)
    return JSONResponse(content=result)

@app.post("/api/align-part")
async def align_part_endpoint(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...), # Original file2 PDF
    threshold: int = Form(30),
    box_size: int = Form(5),
    dilation_iterations: int = Form(0),
    selected_rect: str = Form(...)
):
    img1 = await convert_pdf_to_image(file1)
    img2 = await convert_pdf_to_image(file2)

    # --- Perform global alignment first ---
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
    # --- End global alignment ---

    rect = json.loads(selected_rect)

    # --- 選択部品の位置合わせ ---
    # part_templateはaligned_img2から切り出す
    part_template = aligned_img2.crop((rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h']))
    template_cv = np.array(part_template)
    
    # テンプレートマッチングはaligned_img1に対して行う
    aligned_img1_cv = np.array(img1) # img1は既にグローバルアラインメントの基準なのでそのまま
    res = cv2.matchTemplate(aligned_img1_cv, template_cv, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    new_x, new_y = max_loc

    # aligned_img2をコピーし、部品を新しい位置に貼り付け直す
    modified_aligned_img2 = aligned_img2.copy()
    # 元の位置を白で塗りつぶす
    ImageDraw.Draw(modified_aligned_img2).rectangle(
        (rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h']),
        fill=(255, 255, 255)
    )
    modified_aligned_img2.paste(part_template, (new_x, new_y))

    # 修正後の画像で再比較
    result = run_comparison(img1, modified_aligned_img2, threshold, box_size, dilation_iterations)
    return JSONResponse(content=result)

@app.get("/")
def read_root():
    return {"message": "PDF Diff Checker API"}