from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import asyncio
import math

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

@app.post("/api/diff")
async def create_diff_image(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    threshold: int = Form(30),
    box_size: int = Form(5)  # ハイライトのサイズ
):
    """2つのPDFを比較し、差分をハイライトした画像を生成する"""
    img1_task = asyncio.create_task(convert_pdf_to_image(file1))
    img2_task = asyncio.create_task(convert_pdf_to_image(file2))
    img1, img2 = await asyncio.gather(img1_task, img2_task)

    if img1.size != img2.size:
        raise HTTPException(status_code=400, detail="PDFのページサイズまたは向きが異なります。")

    pixels1 = img1.load()
    pixels2 = img2.load()
    width, height = img1.size

    diff_areas = []
    for y in range(height):
        for x in range(width):
            if color_difference(pixels1[x, y], pixels2[x, y]) > threshold:
                diff_areas.append((x, y))

    output_img = img1.copy()
    if diff_areas:
        draw = ImageDraw.Draw(output_img)
        # 差分ピクセルを受け取ったbox_sizeで描画
        for x, y in diff_areas:
            draw.rectangle([x - box_size, y - box_size, x + box_size, y + box_size], outline="red", width=1)

    buf = io.BytesIO()
    output_img.save(buf, format='PNG')
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")

@app.get("/")
def read_root():
    return {"message": "PDF Diff Checker API"}