
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import asyncio
import cv2
import numpy as np

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

def align_images(img1: Image.Image, img2: Image.Image) -> Image.Image:
    """OpenCVを使って2つの画像の位置を合わせる"""
    # PIL画像をOpenCV画像(numpy.ndarray)に変換
    img1_cv = np.array(img1)
    img2_cv = np.array(img2)

    # グレースケールに変換
    img1_gray = cv2.cvtColor(img1_cv, cv2.COLOR_RGB2GRAY)
    img2_gray = cv2.cvtColor(img2_cv, cv2.COLOR_RGB2GRAY)

    # 高周波ノイズを減らすために浮動小数点数に変換
    img1_float = np.float32(img1_gray)
    img2_float = np.float32(img2_gray)

    # 位相相関法でズレを検出
    shift, _ = cv2.phaseCorrelate(img1_float, img2_float)
    dx, dy = shift

    # アフィン変換行列を作成（検出されたズレと逆方向に補正する）
    rows, cols = img1_gray.shape
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])

    # 2枚目の画像にアフィン変換を適用して位置を補正
    aligned_img2_cv = cv2.warpAffine(img2_cv, M, (cols, rows))

    # OpenCV画像をPIL画像に変換して返す
    return Image.fromarray(aligned_img2_cv)

def color_difference(p1, p2):
    """2つのピクセルの色差を計算する"""
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) + abs(p1[2] - p2[2])

@app.post("/api/diff")
async def create_diff_image(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    threshold: int = Form(30),
    box_size: int = Form(5)
):
    """2つのPDFを比較し、差分をハイライトした画像を生成する"""
    img1_task = asyncio.create_task(convert_pdf_to_image(file1))
    img2_task = asyncio.create_task(convert_pdf_to_image(file2))
    img1, img2 = await asyncio.gather(img1_task, img2_task)

    if img1.size != img2.size:
        raise HTTPException(status_code=400, detail="PDFのページサイズまたは向きが異なります。")

    # ★★★ 位置合わせ処理を追加 ★★★
    aligned_img2 = align_images(img1, img2)

    pixels1 = img1.load()
    pixels2 = aligned_img2.load() # 補正後の画像で比較
    width, height = img1.size

    diff_areas = []
    for y in range(height):
        for x in range(width):
            if color_difference(pixels1[x, y], pixels2[x, y]) > threshold:
                diff_areas.append((x, y))

    output_img = img1.copy()
    if diff_areas:
        draw = ImageDraw.Draw(output_img)
        for x, y in diff_areas:
            draw.rectangle([x - box_size, y - box_size, x + box_size, y + box_size], outline="red", width=1)

    buf = io.BytesIO()
    output_img.save(buf, format='PNG')
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")

@app.get("/")
def read_root():
    return {"message": "PDF Diff Checker API"}
