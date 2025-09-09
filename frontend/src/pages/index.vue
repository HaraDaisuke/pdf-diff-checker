<template>
  <v-container>
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <v-card class="pa-4">
          <v-card-title class="text-h5 text-center mb-4">PDF Diff Checker</v-card-title>
          <v-card-subtitle class="text-center">修正前と修正後のPDFをアップロードして変更箇所を確認します。</v-card-subtitle>

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
                <v-col cols="12">
                    <v-slider
                        v-model="threshold"
                        label="差分検出の閾値"
                        thumb-label
                        :step="5"
                        :min="0"
                        :max="800"
                        :disabled="!file1 || !file2"
                    ></v-slider>
                    <div class="text-caption text-center">値が低いほど、わずかな色の違いも検出します。</div>
                </v-col>
            </v-row>
            <v-row class="mt-2 align-center">
                <v-col cols="12">
                    <v-slider
                        v-model="boxSize"
                        label="ハイライトの太さ"
                        thumb-label
                        :step="1"
                        :min="1"
                        :max="20"
                        :disabled="!file1 || !file2"
                    ></v-slider>
                    <div class="text-caption text-center">値が大きいほど、ハイライトが太くなります。</div>
                </v-col>
            </v-row>
            <v-row class="mt-2 align-center">
                <v-col cols="12">
                    <v-slider
                        v-model="dilationIterations"
                        label="クラスタリング密集度"
                        thumb-label
                        :step="1"
                        :min="0"
                        :max="100"
                        :disabled="!file1 || !file2"
                    ></v-slider>
                    <div class="text-caption text-center">値が大きいほど、近くの部品が結合されます。</div>
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
            </div>
          </v-card-text>
        </v-card>

        <v-card v-if="resultImageUrl || isLoading" class="mt-6">
          <v-card-title class="text-center">比較結果</v-card-title>
          <v-card-actions v-if="resultImageUrl && !isLoading" class="justify-center">
             <v-btn color="secondary" @click="exportToPdf" prepend-icon="mdi-file-export">
                PDFでエクスポート
            </v-btn>
            <v-btn color="teal" @click="alignSelectedPart" :disabled="!selectedPart" prepend-icon="mdi-target-account">
                選択部品を最適位置に移動
            </v-btn>
          </v-card-actions>
          <v-divider></v-divider>
          <v-card-text class="d-flex justify-center align-center pa-0" style="min-height: 400px;">
            <div v-if="isLoading" class="text-center">
              <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
              <p class="mt-4">比較処理を実行中です...</p>
            </div>
            <div v-if="resultImageUrl && !isLoading" style="position: relative; line-height: 0;">
              <v-img
                :src="resultImageUrl"
                alt="比較結果"
                contain
                max-height="80vh"
                :width="imageDimensions.width"
                :height="imageDimensions.height"
              ></v-img>
              <svg v-if="imageDimensions.width > 0" :viewBox="`0 0 ${imageDimensions.width} ${imageDimensions.height}`" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
                <rect
                  v-for="(part, index) in detectedParts"
                  :key="index"
                  :x="part.x"
                  :y="part.y"
                  :width="part.w"
                  :height="part.h"
                  fill="rgba(0, 0, 255, 0.1)"
                  :stroke="selectedPart === part ? '#ff00ff' : '#0000ff'"
                  stroke-width="2"
                  @click="selectPart(part)"
                  style="cursor: pointer;"
                />
              </svg>
            </div>
          </v-card-text>
        </v-card>

      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, watch, reactive } from 'vue';
import jsPDF from 'jspdf';

const file1 = ref(null);
const file2 = ref(null);
const threshold = ref(470);
const boxSize = ref(1);
const dilationIterations = ref(0); // New ref for dilation
const resultImageUrl = ref('');
const detectedParts = ref([]);
const selectedPart = ref(null);
const imageDimensions = reactive({ width: 0, height: 0 });
const isLoading = ref(false);
const error = ref('');

watch([threshold, boxSize, dilationIterations], (newValues, oldValues) => {
  if (file1.value && file2.value) {
    if (newValues[0] !== oldValues[0] || newValues[1] !== oldValues[1] || newValues[2] !== oldValues[2]) {
        comparePdfs();
    }
  }
});

const getImageDimensions = (imageUrl) => {
    const img = new Image();
    img.onload = () => {
        imageDimensions.width = img.naturalWidth;
        imageDimensions.height = img.naturalHeight;
    };
    img.src = imageUrl;
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
  error.value = '';
  resultImageUrl.value = '';
  detectedParts.value = [];
  selectedPart.value = null;

  const formData = new FormData();
  formData.append('file1', pdfFile1);
  formData.append('file2', pdfFile2);
  formData.append('threshold', threshold.value);
  formData.append('box_size', boxSize.value);
  formData.append('dilation_iterations', dilationIterations.value); // Send dilation value

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
    resultImageUrl.value = data.image;
    detectedParts.value = data.rectangles;
    getImageDimensions(data.image);

  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
};

const selectPart = (part) => {
    if (selectedPart.value === part) {
        selectedPart.value = null; // Allow deselecting
    } else {
        selectedPart.value = part;
    }
};

const alignSelectedPart = async () => {
    if (!selectedPart.value || !file1.value || !file2.value) {
        error.value = '部品が選択されていないか、元のPDFが指定されていません。';
        return;
    }

    isLoading.value = true;
    error.value = '';

    const formData = new FormData();
    const pdfFile1 = Array.isArray(file1.value) ? file1.value[0] : file1.value;
    const pdfFile2 = Array.isArray(file2.value) ? file2.value[0] : file2.value;

    formData.append('file1', pdfFile1);
    formData.append('file2', pdfFile2);
    formData.append('threshold', threshold.value);
    formData.append('box_size', boxSize.value);
    formData.append('dilation_iterations', dilationIterations.value); // Send dilation value
    formData.append('selected_rect', JSON.stringify(selectedPart.value));

    try {
        const response = await fetch('http://localhost:8000/api/align-part', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || `サーバーエラー: ${response.statusText}`);
        }

        const data = await response.json();
        resultImageUrl.value = data.image;
        detectedParts.value = data.rectangles;
        getImageDimensions(data.image);
        selectedPart.value = null; // Clear selection after alignment

    } catch (e) {
        error.value = e.message;
    } finally {
        isLoading.value = false;
    }
};

const exportToPdf = () => {
  if (!resultImageUrl.value) return;

  const img = new Image();
  img.onload = () => {
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    const orientation = w > h ? 'l' : 'p';

    const doc = new jsPDF(orientation, 'px', [w, h]);

    doc.addImage(img, 'PNG', 0, 0, w, h);
    doc.save('diff-result.pdf');
  };
  img.onerror = () => {
      error.value = "PDFのエクスポート中に画像の読み込みに失敗しました。"
  }
  img.src = resultImageUrl.value;
};

</script>