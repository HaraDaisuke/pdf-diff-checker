<template>
  <v-container>
    <v-row justify="center">
      <v-col cols="12">
        <v-card class="pa-4">
          <v-card-title class="text-h5 text-center mb-4">全体比較</v-card-title>
          <v-card-subtitle class="text-center">修正前と修正後のPDFをアップロードして、ページごとに変更箇所を確認します。</v-card-subtitle>

          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <v-file-input
                  v-model="file1"
                  label="修正前のPDF"
                  accept=".pdf"
                  prepend-icon="mdi-file-pdf-box"
                  variant="outlined"
                ></v-file-input>
              </v-col>
              <v-col cols="12" md="6">
                <v-file-input
                  v-model="file2"
                  label="修正後のPDF"
                  accept=".pdf"
                  prepend-icon="mdi-file-pdf-box"
                  variant="outlined"
                ></v-file-input>
              </v-col>
            </v-row>

            <v-row class="mt-2 align-center">
                <v-col cols="12" md="3" class="text-subtitle-1 font-weight-medium pr-0">差分検出の閾値</v-col>
                <v-col cols="auto" class="font-weight-medium text-caption">高感度</v-col>
                <v-col>
                    <v-slider
                        v-model="threshold"
                        thumb-label
                        :step="5"
                        :min="0"
                        :max="800"
                        :disabled="!file1 || !file2"
                        hide-details
                    ></v-slider>
                </v-col>
                <v-col cols="auto" class="font-weight-medium text-caption">低感度</v-col>
            </v-row>
            <v-row class="mt-n4">
                <v-col offset-md="3">
                    <div class="text-caption">値が低いほど、わずかな色の違いも検出します。</div>
                </v-col>
            </v-row>
            <v-row class="align-center">
                <v-col cols="12" md="3" class="text-subtitle-1 font-weight-medium pr-0">ハイライトの太さ</v-col>
                <v-col cols="auto" class="font-weight-medium text-caption">細い</v-col>
                <v-col>
                    <v-slider
                        v-model="boxSize"
                        thumb-label
                        :step="1"
                        :min="1"
                        :max="20"
                        :disabled="!file1 || !file2"
                        hide-details
                    ></v-slider>
                </v-col>
                <v-col cols="auto" class="font-weight-medium text-caption">太い</v-col>
            </v-row>
            <v-row class="mt-n4">
                <v-col offset-md="3">
                    <div class="text-caption">値が大きいほど、ハイライトが太くなります。</div>
                </v-col>
            </v-row>

            <v-alert v-if="error" type="error" class="mt-4" dense dismissible>
              {{ error }}
            </v-alert>

            <div class="text-center mt-6">
              <v-btn
                color="primary"
                @click="comparePdfs"
                :disabled="!file1 || !file2"
                :loading="isLoading"
                size="large"
              >
                比較する
              </v-btn>
              <v-btn
                color="secondary"
                class="ml-4"
                size="large"
                :disabled="comparisonResults.length === 0 || isLoading"
                @click="exportToPdf"
                prepend-icon="mdi-file-export"
              >
                PDFでエクスポート
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <div v-if="isLoading" class="text-center mt-10">
          <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
          <p class="mt-4">比較処理を実行中です...</p>
        </div>

        <!-- Results List -->
        <div v-if="comparisonResults.length > 0 && !isLoading" class="mt-6">
          <v-card v-for="result in comparisonResults" :key="result.page_number" class="mb-4">
            <v-card-title class="text-h6">ページ {{ result.page_number }}</v-card-title>
            <v-divider></v-divider>
            <v-row no-gutters>
              <v-col cols="12" md="4">
                <v-card-subtitle class="text-center">修正前</v-card-subtitle>
                <v-img :src="result.image_before" contain aspect-ratio="1.414" class="ma-2"></v-img>
              </v-col>
              <v-col cols="12" md="4">
                <v-card-subtitle class="text-center">修正後</v-card-subtitle>
                <v-img :src="result.image_after" contain aspect-ratio="1.414" class="ma-2"></v-img>
              </v-col>
              <v-col cols="12" md="4">
                <v-card-subtitle class="text-center">比較結果</v-card-subtitle>
                <v-img :src="result.image_diff" contain aspect-ratio="1.414" class="ma-2"></v-img>
              </v-col>
            </v-row>
          </v-card>
        </div>

      </v-col>
    </v-row>

  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { PDFDocument, rgb } from 'pdf-lib';
import fontkit from '@pdf-lib/fontkit';

const file1 = ref(null);
const file2 = ref(null);
const threshold = ref(470);
const boxSize = ref(1);
const comparisonResults = ref([]);
const isLoading = ref(false);
const error = ref('');
const japaneseFont = ref(null);

onMounted(async () => {
  try {
    const fontResponse = await fetch('/NotoSansJP-Regular.ttf');
    if (fontResponse.ok) {
      japaneseFont.value = await fontResponse.arrayBuffer();
    }
  } catch (e) {
    console.error("Could not load Japanese font for PDF export.", e);
  }
});

const resetResults = () => {
  comparisonResults.value = [];
  error.value = '';
};

const comparePdfs = async () => {
  if (!file1.value || !file2.value) {
    error.value = '2つのPDFファイルを指定してください。';
    return;
  }

  const pdfFile1 = Array.isArray(file1.value) ? file1.value[0] : file1.value;
  const pdfFile2 = Array.isArray(file2.value) ? file2.value[0] : file2.value;

  if (!pdfFile1 || !pdfFile2) {
    error.value = '有効なPDFファイルが指定されていません。';
    return;
  }

  isLoading.value = true;
  resetResults();

  const formData = new FormData();
  formData.append('file1', pdfFile1);
  formData.append('file2', pdfFile2);
  formData.append('threshold', threshold.value);
  formData.append('box_size', boxSize.value);
  formData.append('dilation_iterations', 0); // Not used in this UI, but required by API

  try {
    const response = await fetch('http://localhost:8000/api/diff', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(errorData?.detail || `サーバーエラー: ${response.statusText}`);
    }

    const data = await response.json();
    comparisonResults.value = data.results;

  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
};

const exportToPdf = async () => {
  if (comparisonResults.value.length === 0) return;

  try {
    const pdfDoc = await PDFDocument.create();
    let customFont = null;
    if (japaneseFont.value) {
        pdfDoc.registerFontkit(fontkit);
        customFont = await pdfDoc.embedFont(japaneseFont.value);
    }

    for (const result of comparisonResults.value) {
        const beforeImageBytes = await fetch(result.image_before).then(res => res.arrayBuffer());
        const afterImageBytes = await fetch(result.image_after).then(res => res.arrayBuffer());
        const diffImageBytes = await fetch(result.image_diff).then(res => res.arrayBuffer());

        const beforeImage = await pdfDoc.embedPng(beforeImageBytes);
        const afterImage = await pdfDoc.embedPng(afterImageBytes);
        const diffImage = await pdfDoc.embedPng(diffImageBytes);

        const page = pdfDoc.addPage();
        const { width, height } = page.getSize();
        const margin = 40;
        const y = height - margin;

        const title = `ページ ${result.page_number} の比較結果`;
        if (customFont) {
            page.drawText(title, { x: margin, y, font: customFont, size: 18, color: rgb(0, 0, 0) });
        } else {
            page.drawText(`Page ${result.page_number} Comparison Result`, { x: margin, y, size: 18, color: rgb(0, 0, 0) });
        }

        const imageWidth = (width - margin * 2) / 3 - 10;
        const beforeHeight = (imageWidth / beforeImage.width) * beforeImage.height;
        const afterHeight = (imageWidth / afterImage.width) * afterImage.height;
        const diffHeight = (imageWidth / diffImage.width) * diffImage.height;
        const maxImageHeight = Math.max(beforeHeight, afterHeight, diffHeight);

        const imageY = y - 20 - maxImageHeight;

        page.drawImage(beforeImage, { x: margin, y: imageY, width: imageWidth, height: beforeHeight });
        page.drawImage(afterImage, { x: margin + imageWidth + 10, y: imageY, width: imageWidth, height: afterHeight });
        page.drawImage(diffImage, { x: margin + (imageWidth + 10) * 2, y: imageY, width: imageWidth, height: diffHeight });
    }

    const pdfBytes = await pdfDoc.save();
    const blob = new Blob([pdfBytes], { type: 'application/pdf' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'global-comparison-report.pdf';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);

  } catch (e) {
    console.error("PDFのエクスポートに失敗しました。", e);
    error.value = "PDFのエクスポートに失敗しました。";
  }
};

</script>