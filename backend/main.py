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

@app.post("/api/diff")
async def diff_endpoint(file1: UploadFile = File(...), file2: UploadFile = File(...), threshold: int = Form(30), box_size: int = Form(5), dilation_iterations: int = Form(0)):
    img1 = await convert_pdf_to_image(file1)
    img2 = await convert_pdf_to_image(file2)
    result = run_comparison(img1, img2, threshold, box_size, dilation_iterations)
    return JSONResponse(content=result)


@app.post("/api/diff-images")
async def diff_images_endpoint(file1: UploadFile = File(...), file2: UploadFile = File(...), threshold: int = Form(30), box_size: int = Form(5), dilation_iterations: int = Form(0)):
    """
    2つの画像を直接比較し、差分を検出するエンドポイント。
    サイズが異なる場合は、大きい方に合わせて小さい方に余白を追加する。
    """
    try:
        img1_bytes = await file1.read()
        img2_bytes = await file2.read()

        img1 = Image.open(io.BytesIO(img1_bytes)).convert("RGBA")
        img2 = Image.open(io.BytesIO(img2_bytes)).convert("RGBA")

        # サイズが異なる場合の処理
        if img1.size != img2.size:
            max_width = max(img1.width, img2.width)
            max_height = max(img1.height, img2.height)

            # 新しい背景画像を作成 (白色)
            new_img1 = Image.new('RGBA', (max_width, max_height), (255, 255, 255, 255))
            new_img2 = Image.new('RGBA', (max_width, max_height), (255, 255, 255, 255))

            # 元の画像を中央にペースト
            paste_pos1 = ((max_width - img1.width) // 2, (max_height - img1.height) // 2)
            paste_pos2 = ((max_width - img2.width) // 2, (max_height - img2.height) // 2)
            
            new_img1.paste(img1, paste_pos1, img1)
            new_img2.paste(img2, paste_pos2, img2)
            
            img1 = new_img1
            img2 = new_img2

        # 比較処理のためにRGBに変換
        img1 = img1.convert("RGB")
        img2 = img2.convert("RGB")

        result = run_comparison(img1, img2, threshold, box_size, dilation_iterations)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"画像の処理中にエラーが発生しました: {e}")

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


@app.post("/api/crop-by-selection")
async def crop_by_selection_endpoint(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    selection_points: str = Form(...)
):
    try:
        img1 = await convert_pdf_to_image(file1)
        img2 = await convert_pdf_to_image(file2)

        # グローバル位置合わせ
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
        aligned_img1_cv = img1_cv

        # ポリゴンマスクの作成
        points = json.loads(selection_points)
        if not points:
            raise HTTPException(status_code=400, detail="選択範囲の点がありません")
            
        pts = np.array([[p['x'], p['y']] for p in points], dtype=np.int32)
        x, y, w, h = cv2.boundingRect(pts)

        # 座標が画像の範囲外に出ないようにクリッピング
        x = max(0, x)
        y = max(0, y)
        w = min(w, cols - x)
        h = min(h, rows - y)

        # boundingRectで計算されたx,yは全体座標なので、ポリゴンの座標をROI基準に変換
        pts_roi = pts - np.array([x, y])

        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [pts_roi], 255)

        # ROI（関心領域）を切り出し
        roi1 = aligned_img1_cv[y:y+h, x:x+w]
        roi2 = aligned_img2_cv[y:y+h, x:x+w]

        # RGBAに変換してアルファチャンネル（透明度）を追加
        roi1_rgba = cv2.cvtColor(roi1, cv2.COLOR_RGB2RGBA)
        roi2_rgba = cv2.cvtColor(roi2, cv2.COLOR_RGB2RGBA)

        # マスクをアルファチャンネルに適用
        roi1_rgba[:, :, 3] = mask
        roi2_rgba[:, :, 3] = mask

        # PIL画像に変換してBase64エンコード
        cropped_img1 = Image.fromarray(roi1_rgba)
        cropped_img2 = Image.fromarray(roi2_rgba)

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


def _crop_image(image_cv, points_str: str):
    """画像(numpy array)と座標リストのJSON文字列を受け取り、切り抜いたPIL画像を返す"""
    points = json.loads(points_str)
    if not points:
        return None

    rows, cols = image_cv.shape[:2]
    pts = np.array([[p['x'], p['y']] for p in points], dtype=np.int32)
    x, y, w, h = cv2.boundingRect(pts)

    # 座標が画像の範囲外に出ないようにクリッピング
    x = max(0, x)
    y = max(0, y)
    w = min(w, cols - x)
    h = min(h, rows - y)

    # boundingRectで計算されたx,yは全体座標なので、ポリゴンの座標をROI基準に変換
    pts_roi = pts - np.array([x, y])

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts_roi], 255)

    # ROI（関心領域）を切り出し
    roi = image_cv[y:y+h, x:x+w]

    # RGBAに変換してアルファチャンネル（透明度）を追加
    roi_rgba = cv2.cvtColor(roi, cv2.COLOR_RGB2RGBA)

    # マスクをアルファチャンネルに適用
    roi_rgba[:, :, 3] = mask

    return Image.fromarray(roi_rgba)


@app.post("/api/crop-by-independent-selections")
async def crop_by_independent_selections_endpoint(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    selection_points_before: str = Form(...),
    selection_points_after: str = Form(...)
):
    try:
        img1 = await convert_pdf_to_image(file1)
        img2 = await convert_pdf_to_image(file2)

        # グローバル位置合わせ
        img1_cv = np.array(img1)
        img2_cv = np.array(img2)
        img1_gray = cv2.cvtColor(img1_cv, cv2.COLOR_RGB2GRAY)
        img2_gray = cv2.cvtColor(img2_cv, cv2.COLOR_RGB2GRAY)
        shift, _ = cv2.phaseCorrelate(np.float32(img1_gray), np.float32(img2_gray))
        dx, dy = shift
        shift_x, shift_y = -dx, -dy
        M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
        rows, cols = img1_gray.shape
        aligned_img2_cv = cv2.warpAffine(img2_cv, M, (cols, rows))
        aligned_img1_cv = img1_cv

        # それぞれの選択範囲で画像を切り出し
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

@app.get("/")
def read_root():
    return {"message": "PDF Diff Checker API"}