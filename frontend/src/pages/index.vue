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
                <template v-slot:loader>
                  <v-progress-circular indeterminate size="24"></v-progress-circular>
                </template>
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <v-card v-if="resultImageUrl || isLoading" class="mt-6">
          <v-card-title class="text-center">比較結果</v-card-title>
          <v-divider></v-divider>
          <v-card-text class="d-flex justify-center align-center" style="min-height: 400px;">
            <div v-if="isLoading" class="text-center">
              <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
              <p class="mt-4">比較処理を実行中です...</p>
            </div>
            <v-img
              v-if="resultImageUrl && !isLoading"
              :src="resultImageUrl"
              alt="比較結果"
              contain
              max-height="80vh"
            ></v-img>
          </v-card-text>
        </v-card>

      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue';

const file1 = ref(null);
const file2 = ref(null);
const resultImageUrl = ref('');
const isLoading = ref(false);
const error = ref('');

const comparePdfs = async () => {
  if (!file1.value || !file2.value) {
    error.value = '2つのPDFファイルを指定してください。';
    return;
  }

  // v-file-input returns an array even for a single file, so we take the first element.
  const pdfFile1 = Array.isArray(file1.value) ? file1.value[0] : file1.value;
  const pdfFile2 = Array.isArray(file2.value) ? file2.value[0] : file2.value;

  if (!pdfFile1 || !pdfFile2) {
    error.value = '有効なPDFファイルが指定されていません。';
    return;
  }

  isLoading.value = true;
  error.value = '';
  resultImageUrl.value = ''; // 既存の結果をクリア

  const formData = new FormData();
  formData.append('file1', pdfFile1);
  formData.append('file2', pdfFile2);

  try {
    // Note: Ensure the backend is running and CORS is configured for the frontend's origin
    const response = await fetch('http://localhost:8000/api/diff', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null); // JSONパース失敗も考慮
      throw new Error(errorData?.detail || `サーバーエラー: ${response.statusText}`);
    }

    const imageBlob = await response.blob();
    resultImageUrl.value = URL.createObjectURL(imageBlob);

  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
};
</script>
