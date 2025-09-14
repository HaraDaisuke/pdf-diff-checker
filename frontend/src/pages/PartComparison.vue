<template>
  <v-container fluid>
    <!-- Page Selection Modal -->
    <v-dialog v-model="showPageSelectionModal" persistent max-width="90vw">
      <v-card>
        <v-card-title class="text-h5">比較するページを選択</v-card-title>
        <v-card-text>
          <v-row>
            <!-- Before PDF Thumbnails -->
            <v-col cols="6">
              <v-card-subtitle class="text-center">修正前 PDF</v-card-subtitle>
              <v-sheet class="pa-2 overflow-y-auto" max-height="70vh">
                <v-item-group v-model="selectedPageBefore" mandatory>
                  <v-row dense>
                    <v-col v-for="(thumb, index) in thumbnailsBefore" :key="`before-${index}`" cols="12">
                      <v-item v-slot="{ isSelected, toggle }">
                        <v-card 
                          :color="isSelected ? 'primary' : ''"
                          class="d-flex align-center pa-2"
                          @click="toggle"
                        >
                          <span class="mr-4 font-weight-bold">{{ index + 1 }}</span>
                          <v-img :src="thumb" aspect-ratio="1.414" contain height="200"></v-img>
                        </v-card>
                      </v-item>
                    </v-col>
                  </v-row>
                </v-item-group>
              </v-sheet>
            </v-col>

            <!-- After PDF Thumbnails -->
            <v-col cols="6">
              <v-card-subtitle class="text-center">修正後 PDF</v-card-subtitle>
              <v-sheet class="pa-2 overflow-y-auto" max-height="70vh">
                <v-item-group v-model="selectedPageAfter" mandatory>
                  <v-row dense>
                    <v-col v-for="(thumb, index) in thumbnailsAfter" :key="`after-${index}`" cols="12">
                      <v-item v-slot="{ isSelected, toggle }">
                        <v-card 
                          :color="isSelected ? 'primary' : ''"
                          class="d-flex align-center pa-2"
                          @click="toggle"
                        >
                          <span class="mr-4 font-weight-bold">{{ index + 1 }}</span>
                          <v-img :src="thumb" aspect-ratio="1.414" contain height="200"></v-img>
                        </v-card>
                      </v-item>
                    </v-col>
                  </v-row>
                </v-item-group>
              </v-sheet>
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="blue-darken-1" variant="text" @click="cancelPageSelection">キャンセル</v-btn>
          <v-btn 
            color="blue-darken-1" 
            variant="tonal" 
            @click="confirmPageSelection"
            :disabled="selectedPageBefore === null || selectedPageAfter === null"
          >確定</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 1. File Inputs and Controls -->
    <v-card class="mb-4">
      <v-card-text>
        <v-row align="center">
          <v-col cols="12" md="5">
            <v-file-input
              v-model="file1"
              label="修正前のPDF"
              accept=".pdf"
              prepend-icon="mdi-file-pdf-box"
              variant="outlined"
              dense
              hide-details
            ></v-file-input>
          </v-col>
          <v-col cols="12" md="5">
            <v-file-input
              v-model="file2"
              label="修正後のPDF"
              accept=".pdf"
              prepend-icon="mdi-file-pdf-box"
              variant="outlined"
              dense
              hide-details
            ></v-file-input>
          </v-col>
          <v-col cols="12" md="2">
            <v-switch
              v-model="isSyncMode"
              label="左右を連携"
              color="primary"
              inset
              hide-details
            ></v-switch>
          </v-col>
        </v-row>
        <v-row class="mt-2">
            <v-col cols="12" md="6">
                <div class="text-subtitle-1 font-weight-medium">差分検出の閾値</div>
                <v-row align="center" dense class="mt-n2">
                    <v-col cols="auto" class="font-weight-medium text-caption">高感度</v-col>
                    <v-col>
                        <v-slider
                            v-model="diffThreshold"
                            thumb-label
                            :step="5"
                            :min="0"
                            :max="800"
                            hide-details
                        ></v-slider>
                    </v-col>
                    <v-col cols="auto" class="font-weight-medium text-caption">低感度</v-col>
                </v-row>
            </v-col>
            <v-col cols="12" md="6">
                <div class="text-subtitle-1 font-weight-medium">ハイライトの太さ</div>
                <v-row align="center" dense class="mt-n2">
                    <v-col cols="auto" class="font-weight-medium text-caption">細い</v-col>
                    <v-col>
                        <v-slider
                            v-model="highlightThickness"
                            thumb-label
                            :step="1"
                            :min="1"
                            :max="20"
                            hide-details
                        ></v-slider>
                    </v-col>
                    <v-col cols="auto" class="font-weight-medium text-caption">太い</v-col>
                </v-row>
            </v-col>
        </v-row>
        <v-alert v-if="error" type="error" class="mt-4" dense dismissible>
          {{ error }}
        </v-alert>
      </v-card-text>
    </v-card>

    <!-- Loading Indicator -->
    <v-row v-if="isLoading" justify="center" class="my-10">
      <v-col cols="auto">
        <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
        <p class="mt-4">{{ loadingMessage }}</p>
      </v-col>
    </v-row>

    <!-- 2. Main Image Canvases -->
    <v-row v-if="!isLoading && originalBeforeImage">
      <v-col cols="12" md="6">
        <v-card :class="{'selection-pending': isWaitingForSecondSelection && firstSelectionCanvasRef !== canvasBefore}">
          <v-card-title class="text-center">修正前 ({{ selectedPageBefore + 1 }}ページ)</v-card-title>
          <v-divider />
          <div style="position: relative; cursor: crosshair;">
            <canvas 
              ref="canvasBefore"
              @mousedown="startDrawing"
              @mousemove="draw"
              @mouseup="stopDrawing"
              @mouseleave="stopDrawing"
            ></canvas>
          </div>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card :class="{'selection-pending': isWaitingForSecondSelection && firstSelectionCanvasRef !== canvasAfter}">
          <v-card-title class="text-center">修正後 ({{ selectedPageAfter + 1 }}ページ)</v-card-title>
          <v-divider />
          <div style="position: relative; cursor: crosshair;">
            <canvas 
              ref="canvasAfter"
              @mousedown="startDrawing"
              @mousemove="draw"
              @mouseup="stopDrawing"
              @mouseleave="stopDrawing"
            ></canvas>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- 3. Cropped Images List -->
    <v-card class="mt-4 mb-16" v-if="croppedPairs.length > 0">
      <v-card-title>切り出しリスト</v-card-title>
      <v-card-subtitle>ドラッグ＆ドロップで順番を入れ替えられます。</v-card-subtitle>

      <!-- Header Row -->
      <v-row class="pa-2 text-center font-weight-bold" no-gutters>
        <v-col cols="1">No.</v-col>
        <v-col cols="10">
            <v-row no-gutters>
                <v-col cols="4">修正前</v-col>
                <v-col cols="4">修正後</v-col>
                <v-col cols="4">比較結果</v-col>
            </v-row>
        </v-col>
        <v-col cols="1">操作</v-col>
      </v-row>

      <v-divider />
      <v-list class="pa-0">
        <div v-for="(pair, index) in croppedPairs" :key="pair.id">
            <v-list-item
                :draggable="true"
                @dragstart="onDragStart($event, index)"
                @dragover.prevent
                @drop="onDrop($event, index)"
                class="draggable-item"
            >
                <v-row align="center" no-gutters>
                    <v-col cols="1" class="text-center d-flex align-center justify-center">
                        <v-icon small>mdi-drag-vertical</v-icon>
                        <span>{{ index + 1 }}</span>
                    </v-col>
                    <v-col cols="10">
                        <v-row no-gutters>
                            <v-col cols="4" class="pa-2">
                                <v-card elevation="2">
                                    <v-img :src="pair.before" contain aspect-ratio="1.4"/>
                                </v-card>
                            </v-col>
                            <v-col cols="4" class="pa-2">
                                <v-card elevation="2">
                                    <v-img :src="pair.after" contain aspect-ratio="1.4"/>
                                </v-card>
                            </v-col>
                            <v-col cols="4" class="pa-2">
                                <v-card elevation="2" class="d-flex align-center justify-center" style="height: 100%;">
                                    <v-img v-if="pair.diff" :src="pair.diff" contain aspect-ratio="1.4"/>
                                    <div v-else class="text-center text-disabled">比較待ち</div>
                                </v-card>
                            </v-col>
                        </v-row>
                    </v-col>
                    <v-col cols="1" class="text-center">
                        <v-btn icon small @click="toggleComment(pair)"><v-icon>mdi-comment-plus-outline</v-icon></v-btn>
                        <v-btn icon small @click="removePair(pair.id)"><v-icon>mdi-delete</v-icon></v-btn>
                    </v-col>
                </v-row>
            </v-list-item>
            <v-expand-transition>
                <div v-show="pair.showComment" class="pa-4 pt-0">
                    <v-textarea
                        v-model="pair.comment"
                        label="コメント"
                        rows="2"
                        auto-grow
                        variant="outlined"
                        hide-details
                    ></v-textarea>
                </div>
            </v-expand-transition>
            <v-divider />
        </div>
      </v-list>
    </v-card>

    <v-footer app class="justify-center" style="background-color: transparent; padding-bottom: 16px;">
        <v-btn x-large color="success" @click="compareAllPairs" :disabled="croppedPairs.length === 0" :loading="isComparing">
            <v-icon left>mdi-select-compare</v-icon>
            選択範囲をすべて比較
        </v-btn>
        <v-btn x-large color="secondary" class="ml-4" @click="exportToPdf" :disabled="!allPairsCompared">
            <v-icon left>mdi-file-export</v-icon>
            PDFでエクスポート
        </v-btn>
    </v-footer>

  </v-container>
</template>

<style scoped>
.selection-pending {
  border: 2px solid #ff00ff;
  box-shadow: 0 0 10px #ff00ff;
}
.draggable-item {
  cursor: move;
}
</style>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import { PDFDocument, rgb } from 'pdf-lib';
import fontkit from '@pdf-lib/fontkit';

// --- reactive state ---
const file1 = ref(null);
const file2 = ref(null);
const isLoading = ref(false);
const loadingMessage = ref('画像を読み込み中です...');
const isComparing = ref(false);
const error = ref('');
const originalBeforeImage = ref(null);
const originalAfterImage = ref(null);
const canvasBefore = ref(null);
const canvasAfter = ref(null);
const croppedPairs = ref([]);
const diffThreshold = ref(500);
const highlightThickness = ref(2);
const japaneseFont = ref(null); // Holds the font ArrayBuffer
const isSyncMode = ref(false);
const isWaitingForSecondSelection = ref(false);
const firstSelectionCanvasRef = ref(null);
const selectionBeforePoints = ref([]);
const selectionAfterPoints = ref([]);
const isDrawing = ref(false);
const currentDrawingPoints = ref([]);
const nativeBeforeImageSize = ref({ width: 0, height: 0 });
const nativeAfterImageSize = ref({ width: 0, height: 0 });
const draggedIndex = ref(null);

// --- Page Selection Modal State ---
const showPageSelectionModal = ref(false);
const thumbnailsBefore = ref([]);
const thumbnailsAfter = ref([]);
const selectedPageBefore = ref(null);
const selectedPageAfter = ref(null);

// --- computed ---
const allPairsCompared = computed(() => {
  return croppedPairs.value.length > 0 && croppedPairs.value.every(p => p.diff);
});

// --- watchers ---
watch([file1, file2], ([newFile1, newFile2]) => {
  if (newFile1 && newFile2) {
    openPageSelectionModal();
  }
});

watch(originalBeforeImage, (newValue) => {
  if (newValue) redrawAllCanvases();
}, { flush: 'post' });

watch(isSyncMode, () => {
  isWaitingForSecondSelection.value = false;
  firstSelectionCanvasRef.value = null;
  if (originalBeforeImage.value) redrawAllCanvases();
});

// --- lifecycle hooks ---
onMounted(async () => {
  window.addEventListener('resize', redrawAllCanvases);
  try {
    const fontResponse = await fetch('/NotoSansJP-Regular.ttf');
    if (!fontResponse.ok) throw new Error('Font fetch failed');
    japaneseFont.value = await fontResponse.arrayBuffer();
  } catch (e) {
    console.error("Japanese font failed to load:", e);
    error.value = "PDF出力用の日本語フォントが読み込めませんでした。";
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', redrawAllCanvases);
});

// --- methods ---

const openPageSelectionModal = async () => {
  isLoading.value = true;
  loadingMessage.value = 'PDFのサムネイルを生成中です...';
  error.value = '';
  try {
    const [thumbs1, thumbs2] = await Promise.all([
      fetchThumbnails(file1.value),
      fetchThumbnails(file2.value)
    ]);
    thumbnailsBefore.value = thumbs1;
    thumbnailsAfter.value = thumbs2;
    selectedPageBefore.value = 0;
    selectedPageAfter.value = 0;
    showPageSelectionModal.value = true;
  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
};

const fetchThumbnails = async (file) => {
  const pdfFile = Array.isArray(file) ? file[0] : file;
  const formData = new FormData();
  formData.append('file', pdfFile);
  const response = await fetch('http://localhost:8000/api/pdf-thumbnails', { method: 'POST', body: formData });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'サムネイルの取得に失敗しました。' }));
    throw new Error(err.detail);
  }
  const data = await response.json();
  return data.thumbnails;
};

const cancelPageSelection = () => {
  showPageSelectionModal.value = false;
  file1.value = null;
  file2.value = null;
};

const confirmPageSelection = async () => {
  showPageSelectionModal.value = false;
  await loadSelectedPages();
};

const loadSelectedPages = async () => {
  const pdfFile1 = Array.isArray(file1.value) ? file1.value[0] : file1.value;
  const pdfFile2 = Array.isArray(file2.value) ? file2.value[0] : file2.value;

  if (!pdfFile1 || !pdfFile2 || selectedPageBefore.value === null || selectedPageAfter.value === null) {
    error.value = '比較するページが選択されていません。';
    return;
  }

  isLoading.value = true;
  loadingMessage.value = '選択されたページを読み込んでいます...';
  error.value = '';
  originalBeforeImage.value = null;
  originalAfterImage.value = null;
  croppedPairs.value = [];

  const formData = new FormData();
  formData.append('file1', pdfFile1);
  formData.append('file2', pdfFile2);
  formData.append('page_num1', selectedPageBefore.value);
  formData.append('page_num2', selectedPageAfter.value);

  try {
    const response = await fetch('http://localhost:8000/api/get-pdf-pages', { method: 'POST', body: formData });
    if (!response.ok) { 
        const err = await response.json().catch(() => ({ detail: 'サーバーエラーが発生しました。' })); 
        throw new Error(err.detail); 
    }
    const data = await response.json();
    originalBeforeImage.value = data.image_before;
    originalAfterImage.value = data.image_after;
  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
};

const getCanvasContext = (canvasEl) => canvasEl.getContext('2d');

const renderImageOnCanvas = (canvasEl, imageSrc, nativeSizeRef) => {
  return new Promise((resolve, reject) => {
    if (!canvasEl) return reject(new Error("Canvas element not found"));
    const img = new Image();
    img.onload = () => {
      nativeSizeRef.value = { width: img.naturalWidth, height: img.naturalHeight };
      const container = canvasEl.parentElement;
      if (!container) return reject(new Error("Canvas container not found"));
      const containerWidth = container.clientWidth;
      if (containerWidth === 0) {
        setTimeout(() => renderImageOnCanvas(canvasEl, imageSrc, nativeSizeRef).then(resolve).catch(reject), 100);
        return;
      }
      const aspectRatio = img.naturalWidth / img.naturalHeight;
      canvasEl.width = containerWidth;
      canvasEl.height = containerWidth / aspectRatio;
      const ctx = getCanvasContext(canvasEl);
      ctx.drawImage(img, 0, 0, canvasEl.width, canvasEl.height);
      resolve();
    };
    img.onerror = (err) => reject(err);
    img.src = imageSrc;
  });
};

const redrawAllCanvases = async () => {
  if (!originalBeforeImage.value || !originalAfterImage.value || !canvasBefore.value || !canvasAfter.value) return;
  try {
    await Promise.all([
      renderImageOnCanvas(canvasBefore.value, originalBeforeImage.value, nativeBeforeImageSize),
      renderImageOnCanvas(canvasAfter.value, originalAfterImage.value, nativeAfterImageSize)
    ]);
  } catch (e) {
    error.value = "画像の再描画中にエラーが発生しました。";
    console.error(e);
  }
};

const getMousePos = (canvasEl, evt) => {
  const rect = canvasEl.getBoundingClientRect();
  return { x: evt.clientX - rect.left, y: evt.clientY - rect.top };
};

const startDrawing = (event) => {
  if (isSyncMode.value === false && isWaitingForSecondSelection.value === true && firstSelectionCanvasRef.value === event.target) {
      return;
  }
  isDrawing.value = true;
  if (!isWaitingForSecondSelection.value) {
      redrawAllCanvases();
  }
  currentDrawingPoints.value = [getMousePos(event.target, event)];
  const ctx = getCanvasContext(event.target);
  ctx.beginPath();
  ctx.moveTo(currentDrawingPoints.value[0].x, currentDrawingPoints.value[0].y);
};

const draw = (event) => {
  if (!isDrawing.value) return;
  const pos = getMousePos(event.target, event);
  currentDrawingPoints.value.push(pos);
  
  const canvases = isSyncMode.value ? [canvasBefore.value, canvasAfter.value] : [event.target];
  canvases.forEach(canvas => {
      if (!canvas) return;
      const ctx = getCanvasContext(canvas);
      ctx.lineTo(pos.x, pos.y);
      ctx.strokeStyle = '#ff00ff';
      ctx.lineWidth = 2;
      ctx.stroke();
  });
};

const stopDrawing = async (event) => {
  if (!isDrawing.value) return;
  isDrawing.value = false;
  if (currentDrawingPoints.value.length < 3) {
      redrawAllCanvases();
      return;
  }

  const canvases = isSyncMode.value ? [canvasBefore.value, canvasAfter.value] : [event.target];
  canvases.forEach(canvas => {
      if (!canvas) return;
      const ctx = getCanvasContext(canvas);
      ctx.closePath();
      ctx.fillStyle = 'rgba(255, 0, 255, 0.2)';
      ctx.fill();
  });

  if (isSyncMode.value) {
      await cropAndAddPair({ before: currentDrawingPoints.value, after: currentDrawingPoints.value });
  } else {
      if (!isWaitingForSecondSelection.value) {
          isWaitingForSecondSelection.value = true;
          firstSelectionCanvasRef.value = event.target;
          if (event.target === canvasBefore.value) {
              selectionBeforePoints.value = [...currentDrawingPoints.value];
          } else {
              selectionAfterPoints.value = [...currentDrawingPoints.value];
          }
      } else {
          if (event.target === canvasBefore.value) {
              selectionBeforePoints.value = [...currentDrawingPoints.value];
          } else {
              selectionAfterPoints.value = [...currentDrawingPoints.value];
          }
          await cropAndAddPair({ before: selectionBeforePoints.value, after: selectionAfterPoints.value });
          isWaitingForSecondSelection.value = false;
          firstSelectionCanvasRef.value = null;
      }
  }
};

const cropAndAddPair = async ({ before: beforePoints, after: afterPoints }) => {
    if (!canvasBefore.value || !canvasAfter.value) return;

    const scaleBefore = nativeBeforeImageSize.value.width / canvasBefore.value.width;
    const nativeBefore = beforePoints.map(p => ({ x: Math.round(p.x * scaleBefore), y: Math.round(p.y * scaleBefore) }));

    const scaleAfter = nativeAfterImageSize.value.width / canvasAfter.value.width;
    const nativeAfter = afterPoints.map(p => ({ x: Math.round(p.x * scaleAfter), y: Math.round(p.y * scaleAfter) }));

    const formData = new FormData();
    const pdfFile1 = Array.isArray(file1.value) ? file1.value[0] : file1.value;
    const pdfFile2 = Array.isArray(file2.value) ? file2.value[0] : file2.value;
    formData.append('file1', pdfFile1);
    formData.append('file2', pdfFile2);
    formData.append('page_num1', selectedPageBefore.value);
    formData.append('page_num2', selectedPageAfter.value);

    let url;
    if (isSyncMode.value) {
        url = 'http://localhost:8000/api/crop-by-selection';
        formData.append('selection_points', JSON.stringify(nativeBefore));
    } else {
        url = 'http://localhost:8000/api/crop-by-independent-selections';
        formData.append('selection_points_before', JSON.stringify(nativeBefore));
        formData.append('selection_points_after', JSON.stringify(nativeAfter));
    }

    isLoading.value = true;
    loadingMessage.value = '部分領域を切り出し中です...';
    try {
        const response = await fetch(url, { method: 'POST', body: formData });
        if (!response.ok) { const err = await response.json(); throw new Error(err.detail); }
        const data = await response.json();
        croppedPairs.value.push({ 
            id: Date.now(), 
            before: data.cropped_before, 
            after: data.cropped_after, 
            diff: null,
            comment: '',
            showComment: false
        });
        setTimeout(redrawAllCanvases, 100);
    } catch (e) {
        error.value = e.message;
        setTimeout(redrawAllCanvases, 100);
    } finally {
        isLoading.value = false;
    }
};

const dataURLtoBlob = (dataurl) => {
    let arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1], bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
    while(n--){ u8arr[n] = bstr.charCodeAt(n); }
    return new Blob([u8arr], {type:mime});
}

const compareAllPairs = async () => {
  isComparing.value = true;
  error.value = '';
  for (const pair of croppedPairs.value) {
    if (pair.diff) continue;
    try {
      const formData = new FormData();
      formData.append('file1', dataURLtoBlob(pair.before), 'before.png');
      formData.append('file2', dataURLtoBlob(pair.after), 'after.png');
      formData.append('threshold', diffThreshold.value);
      formData.append('box_size', highlightThickness.value);
      formData.append('dilation_iterations', '0');
      const response = await fetch('http://localhost:8000/api/diff-images', { method: 'POST', body: formData });
      if (!response.ok) { console.error(`Failed to compare pair ${pair.id}`); continue; }
      const data = await response.json();
      pair.diff = data.image_diff;
    } catch (e) {
      console.error(`Error comparing pair ${pair.id}:`, e);
      error.value = `ペア ${pair.id} の比較中にエラーが発生しました。`;
    }
  }
  isComparing.value = false;
};

const exportToPdf = async () => {
  if (!japaneseFont.value) {
    error.value = "PDF出力用の日本語フォントが読み込まれていません。ページをリロードしてみてください。";
    return;
  }

  try {
    const pdfDoc = await PDFDocument.create();
    pdfDoc.registerFontkit(fontkit);
    const customFont = await pdfDoc.embedFont(japaneseFont.value);
    
    let page = pdfDoc.addPage();
    const { width, height } = page.getSize();
    const margin = 40;
    const contentWidth = width - (margin * 2);
    const colWidth = contentWidth / 4;
    const imageWidth = colWidth - 15;
    let y = height - margin;

    const title = '部分比較レポート';
    const titleWidth = customFont.widthOfTextAtSize(title, 18);
    page.drawText(title, {
      x: width / 2 - titleWidth / 2,
      y: y,
      font: customFont,
      size: 18,
      color: rgb(0, 0, 0),
    });
    y -= 30;

    const drawHeader = () => {
      page.setFont(customFont);
      page.setFontSize(12);
      page.drawText('No.', { x: margin + 5, y: y });
      page.drawText('修正前', { x: margin + colWidth, y: y });
      page.drawText('修正後', { x: margin + colWidth * 2, y: y });
      page.drawText('比較結果', { x: margin + colWidth * 3, y: y });
      y -= 10;
      page.drawLine({ start: { x: margin, y: y }, end: { x: width - margin, y: y }, thickness: 0.5 });
      y -= 10;
    };

    drawHeader();

    for (let i = 0; i < croppedPairs.value.length; i++) {
      const pair = croppedPairs.value[i];
      if (!pair.diff) continue;

      const beforeImageBytes = await fetch(pair.before).then(res => res.arrayBuffer());
      const afterImageBytes = await fetch(pair.after).then(res => res.arrayBuffer());
      const diffImageBytes = await fetch(pair.diff).then(res => res.arrayBuffer());

      const beforeImage = await pdfDoc.embedPng(beforeImageBytes);
      const afterImage = await pdfDoc.embedPng(afterImageBytes);
      const diffImage = await pdfDoc.embedPng(diffImageBytes);

      const imageHeight = (imageWidth / beforeImage.width) * beforeImage.height;
      
      let commentHeight = 0;
      const commentFontSize = 9;
      const commentLineHeight = commentFontSize * 1.2;
      let commentLines = [];
      if (pair.comment) {
          const comment = `コメント: ${pair.comment}`;
          const commentCharsPerLine = Math.floor(((colWidth * 3 - 15) / (commentFontSize * 0.6)));
          let textLeft = comment;
          while(textLeft.length > 0) {
              commentLines.push(textLeft.substring(0, commentCharsPerLine));
              textLeft = textLeft.substring(commentCharsPerLine);
          }
          commentHeight = commentLines.length * commentLineHeight + 10;
      }

      const rowHeight = imageHeight + commentHeight + 10;

      if (y - rowHeight < margin) {
        page = pdfDoc.addPage();
        y = height - margin;
        drawHeader();
      }

      page.drawText(String(i + 1), { x: margin + 5, y: y - imageHeight / 2, font: customFont, size: 12 });
      page.drawImage(beforeImage, { x: margin + colWidth, y: y - imageHeight, width: imageWidth, height: imageHeight });
      page.drawImage(afterImage, { x: margin + colWidth * 2, y: y - imageHeight, width: imageWidth, height: imageHeight });
      page.drawImage(diffImage, { x: margin + colWidth * 3, y: y - imageHeight, width: imageWidth, height: imageHeight });
      y -= imageHeight;

      if (pair.comment) {
          y -= 10;
          commentLines.forEach(line => {
              page.drawText(line, { x: margin + colWidth, y: y, font: customFont, size: commentFontSize, color: rgb(0.2, 0.2, 0.2) });
              y -= commentLineHeight;
          });
      }

      y -= 10;
      page.drawLine({ start: { x: margin, y: y }, end: { x: width - margin, y: y }, thickness: 0.2, color: rgb(0.8, 0.8, 0.8) });
      y -= 10;
    }

    const pdfBytes = await pdfDoc.save();
    const blob = new Blob([pdfBytes], { type: 'application/pdf' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'part-comparison-report.pdf';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);

  } catch (e) {
    console.error("PDFのエクスポートに失敗しました。", e);
    error.value = "PDFのエクスポートに失敗しました。";
  }
};

const removePair = (id) => {
    croppedPairs.value = croppedPairs.value.filter(p => p.id !== id);
}

const toggleComment = (pair) => {
    pair.showComment = !pair.showComment;
}

const onDragStart = (event, index) => {
  draggedIndex.value = index;
  event.dataTransfer.effectAllowed = 'move';
};

const onDrop = (event, targetIndex) => {
  if (draggedIndex.value === null || draggedIndex.value === targetIndex) return;
  const draggedItem = croppedPairs.value.splice(draggedIndex.value, 1)[0];
  croppedPairs.value.splice(targetIndex, 0, draggedItem);
  draggedIndex.value = null;
};
</script>