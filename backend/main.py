from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import asyncio

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
        # 最初のページを高解像度で画像に変換
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes()))
        doc.close()
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDFの画像化に失敗しました: {e}")

@app.post("/api/diff")
async def create_diff_image(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    """2つのPDFを比較し、差分をハイライトした画像を生成する"""
    # PDFを画像に変換
    img1_task = asyncio.create_task(convert_pdf_to_image(file1))
    img2_task = asyncio.create_task(convert_pdf_to_image(file2))
    img1, img2 = await asyncio.gather(img1_task, img2_task)

    # 画像サイズが異なる場合はエラー
    if img1.size != img2.size:
        raise HTTPException(status_code=400, detail="PDFのページサイズまたは向きが異なります。")

    # ピクセル単位で比較
    pixels1 = img1.load()
    pixels2 = img2.load()
    width, height = img1.size

    diff_areas = []
    # 差分検出（簡略版）
    # パフォーマンス向上のため、一定のブロック単位でチェックすることも可能
    for y in range(height):
        for x in range(width):
            if pixels1[x, y] != pixels2[x, y]:
                diff_areas.append((x, y))

    if not diff_areas:
        # 差分がない場合は、元の画像をそのまま返す
        buf = io.BytesIO()
        img1.save(buf, format='PNG')
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")


    # 差分箇所にハイライトを描画
    output_img = img1.copy()
    draw = ImageDraw.Draw(output_img)
    
    # 差分ピクセルを元に矩形を描画
    # ここでは簡略化のため、個々のピクセルを少し広げて描画
    for x, y in diff_areas:
        draw.rectangle([x-2, y-2, x+2, y+2], outline="red", width=1)


    # 生成した画像をメモリ上でPNG形式で保存
    buf = io.BytesIO()
    output_img.save(buf, format='PNG')
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")

@app.get("/")
def read_root():
    return {"message": "PDF Diff Checker API"}