# pdf-diff-checker

## 概要

製造業で利用される設計図面PDFの修正前後を比較し、変更箇所を迅速かつ正確に検出するためのWebシステムです。従来のピクセル単位の差分検出に加え、スキャン時の微妙な位置ズレを自動補正する高度な機能を提供します。

## 主な機能

### 全体比較モード
- 2つのPDFをアップロードし、ページ全体の差分をハイライト表示します。
- 差分検出の閾値や、ハイライトの太さをリアルタイムで調整可能です。
- 表示されている差分画像をPDFとしてエクスポートできます。

### 部分比較モード
- 2つのPDFから、比較したい部分を複数選択し、リストとして一覧表示します。
- 選択した部分ごとに「修正前」「修正後」「比較結果」の画像を並べて確認できます。
- 各比較項目に対して、**日本語でコメントを記録**できます。
- リスト全体を、**コメントも含めて1つのPDFレポートとして出力**できます。

## 技術スタック

### バックエンド
- **Python 3.8+**
- **FastAPI**: Webフレームワーク
- **ライブラリ**:
  - `PyMuPDF`: PDFからの画像抽出
  - `OpenCV`: 画像処理、差分検出
  - `Pillow`: 画像処理
  - `Numpy`: 数値計算

### フロントエンド
- **Node.js**
- **Vue.js**: JavaScriptフレームワーク
- **Vuetify**: UIコンポーネントフレームワーク
- **ライブラリ**:
  - `pdf-lib`: PDF生成
  - `@pdf-lib/fontkit`: PDFへのカスタムフォント埋め込み

## セットアップ

### 1. プロジェクトのクローン
```bash
git clone [リポジトリのURL]
cd pdf-diff-checker
```

### 2. バックエンドのセットアップ
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windowsの場合は .\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. フロントエンドのセットアップ

#### a. ライブラリのインストール
```bash
cd frontend
npm install
```

#### b. 日本語フォントの配置 (PDF出力用)
部分比較レポートで日本語を正しく表示するために、フォントファイルが必要です。

1. [Google FontsのNoto Sans JPのページ](https://fonts.google.com/specimen/Noto+Sans+JP)にアクセスします。
2. 「Download family」ボタンをクリックし、フォントをダウンロード・解凍します。
3. 解凍したフォルダ内の`static/NotoSansJP-Regular.ttf`ファイルを、このプロジェクトの`frontend/public/`ディレクトリにコピーします。

## 実行方法

### 1. バックエンドサーバーの起動
新しいターミナルを開き、以下を実行します。
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload
```

### 2. フロントエンド開発サーバーの起動
別のターミナルを開き、以下を実行します。
```bash
cd frontend
npm run dev
```

ブラウザで `npm run dev` の出力に表示されるURL (通常は `http://localhost:5173`) にアクセスしてください。