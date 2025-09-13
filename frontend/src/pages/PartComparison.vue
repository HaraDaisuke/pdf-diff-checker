<template>
  <v-container fluid>
    <!-- 1. File Inputs and Controls -->
    <v-card class="mb-4">
      <v-card-text>
        <v-row align="center">
          <v-col cols="12" md="4">
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
          <v-col cols="12" md="4">
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
            <v-btn color="primary" @click="loadPdfs" :disabled="!file1 || !file2" block>
              表示
            </v-btn>
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
        <v-row>
            <v-col cols="12" md="6">
                <v-slider
                    v-model="diffThreshold"
                    label="差分検出の閾値"
                    thumb-label
                    :step="5"
                    :min="0"
                    :max="800"
                    hide-details
                ></v-slider>
            </v-col>
            <v-col cols="12" md="6">
                <v-slider
                    v-model="highlightThickness"
                    label="ハイライトの太さ"
                    thumb-label
                    :step="1"
                    :min="1"
                    :max="20"
                    hide-details
                ></v-slider>
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
        <p class="mt-4">画像を読み込み中です...</p>
      </v-col>
    </v-row>

    <!-- 2. Main Image Canvases -->
    <v-row v-if="!isLoading && originalBeforeImage">
      <v-col cols="12" md="6">
        <v-card :class="{'selection-pending': isWaitingForSecondSelection && firstSelectionCanvasRef !== canvasBefore}">
          <v-card-title class="text-center">修正前</v-card-title>
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
          <v-card-title class="text-center">修正後</v-card-title>
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
                        <v-btn icon small @click="removePair(pair.id)"><v-icon>mdi-delete</v-icon></v-btn>
                    </v-col>
                </v-row>
            </v-list-item>
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
import { ref, nextTick, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import jsPDF from 'jspdf';

const file1 = ref(null);
const file2 = ref(null);

const isLoading = ref(false);
const isComparing = ref(false);
const error = ref('');

const originalBeforeImage = ref(null);
const originalAfterImage = ref(null);

const canvasBefore = ref(null);
const canvasAfter = ref(null);

const croppedPairs = ref([]);

const diffThreshold = ref(500);
const highlightThickness = ref(2);

// --- Mode State ---
const isSyncMode = ref(true);
const isWaitingForSecondSelection = ref(false);
const firstSelectionCanvasRef = ref(null);
const selectionBeforePoints = ref([]);
const selectionAfterPoints = ref([]);

// --- Drawing State ---
const isDrawing = ref(false);
const currentDrawingPoints = ref([]);
const nativeImageSize = ref({ width: 0, height: 0 });

// --- Drag and Drop State ---
const draggedIndex = ref(null);

const allPairsCompared = computed(() => {
  return croppedPairs.value.length > 0 && croppedPairs.value.every(p => p.diff);
});

// Watch for the image sources to change, then redraw the canvases.
// flush: 'post' ensures this runs after Vue has updated the DOM.
watch(originalBeforeImage, (newValue) => {
  if (newValue) {
    redrawAllCanvases();
  }
}, { flush: 'post' });

watch(isSyncMode, () => {
  // Reset pending selections when mode changes
  isWaitingForSecondSelection.value = false;
  firstSelectionCanvasRef.value = null;
  if (originalBeforeImage.value) {
      redrawAllCanvases();
  }
});

const getCanvasContext = (canvasEl) => canvasEl.getContext('2d');

const renderImageOnCanvas = (canvasEl, imageSrc) => {
  return new Promise((resolve, reject) => {
    if (!canvasEl) return reject(new Error("Canvas element not found"));
    const img = new Image();
    img.onload = () => {
      nativeImageSize.value = { width: img.naturalWidth, height: img.naturalHeight };
      const container = canvasEl.parentElement;
      if (!container) return reject(new Error("Canvas container not found"));
      const containerWidth = container.clientWidth;
      if (containerWidth === 0) {
          // If container is not rendered, wait and try again.
          setTimeout(() => renderImageOnCanvas(canvasEl, imageSrc).then(resolve).catch(reject), 100);
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
    if (!originalBeforeImage.value || !originalAfterImage.value) return;
    if (!canvasBefore.value || !canvasAfter.value) {
        error.value = "キャンバスの準備に失敗しました。";
        return;
    }
    try {
        await Promise.all([
            renderImageOnCanvas(canvasBefore.value, originalBeforeImage.value),
            renderImageOnCanvas(canvasAfter.value, originalAfterImage.value)
        ]);
    } catch (e) {
        error.value = "画像の再描画中にエラーが発生しました。";
        console.error(e);
    }
}

const loadPdfs = async () => {
  if (!file1.value || !file2.value) { error.value = '2つのPDFファイルを指定してください。'; return; }
  const pdfFile1 = Array.isArray(file1.value) ? file1.value[0] : file1.value;
  const pdfFile2 = Array.isArray(file2.value) ? file2.value[0] : file2.value;
  if (!pdfFile1 || !pdfFile2) { error.value = '有効なPDFファイルが指定されていません。'; return; }

  isLoading.value = true;
  error.value = '';
  originalBeforeImage.value = null;
  originalAfterImage.value = null;
  croppedPairs.value = [];

  const formData = new FormData();
  formData.append('file1', pdfFile1);
  formData.append('file2', pdfFile2);
  formData.append('threshold', '0'); formData.append('box_size', '0'); formData.append('dilation_iterations', '0');

  try {
    const response = await fetch('http://localhost:8000/api/diff', { method: 'POST', body: formData });
    if (!response.ok) { const err = await response.json(); throw new Error(err.detail); }
    const data = await response.json();
    // This will trigger the watcher to call redrawAllCanvases
    originalBeforeImage.value = data.image_before;
    originalAfterImage.value = data.image_after;
  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
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
    if (!canvasBefore.value) return;
    const scale = nativeImageSize.value.width / canvasBefore.value.width;
    const nativeBefore = beforePoints.map(p => ({ x: Math.round(p.x * scale), y: Math.round(p.y * scale) }));
    const nativeAfter = afterPoints.map(p => ({ x: Math.round(p.x * scale), y: Math.round(p.y * scale) }));

    const formData = new FormData();
    const pdfFile1 = Array.isArray(file1.value) ? file1.value[0] : file1.value;
    const pdfFile2 = Array.isArray(file2.value) ? file2.value[0] : file2.value;
    formData.append('file1', pdfFile1);
    formData.append('file2', pdfFile2);

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
    try {
        const response = await fetch(url, { method: 'POST', body: formData });
        if (!response.ok) { const err = await response.json(); throw new Error(err.detail); }
        const data = await response.json();
        croppedPairs.value.push({ id: Date.now(), before: data.cropped_before, after: data.cropped_after, diff: null });
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
  const doc = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' });
  const margin = 10;
  const pageHeight = doc.internal.pageSize.getHeight();
  const pageWidth = doc.internal.pageSize.getWidth();
  const contentWidth = pageWidth - (margin * 2);
  const colWidth = contentWidth / 4;
  const imageWidth = colWidth - 5;
  let y = margin;

  // PDF Title
  doc.setFontSize(16);
  doc.text('Part Comparison Report', pageWidth / 2, y, { align: 'center' });
  y += 10;

  // Table Header
  doc.setFontSize(12);
  doc.text('No.', margin + 5, y);
  doc.text('Before', margin + colWidth, y);
  doc.text('After', margin + colWidth * 2, y);
  doc.text('Result', margin + colWidth * 3, y);
  y += 5;
  doc.setDrawColor(0);
  doc.line(margin, y, pageWidth - margin, y);
  y += 2;

  for (let i = 0; i < croppedPairs.value.length; i++) {
    const pair = croppedPairs.value[i];
    if (!pair.diff) continue;

    const img = new Image();
    img.src = pair.before;
    await new Promise(resolve => img.onload = resolve);
    const aspectRatio = img.naturalWidth / img.naturalHeight;
    const imageHeight = imageWidth / aspectRatio;
    const rowHeight = imageHeight + 4; // image + padding

    if (y + rowHeight > pageHeight - margin) {
      doc.addPage();
      y = margin;
      // Redraw header on new page
      doc.setFontSize(12);
      doc.text('No.', margin + 5, y);
      doc.text('Before', margin + colWidth, y);
      doc.text('After', margin + colWidth * 2, y);
      doc.text('Result', margin + colWidth * 3, y);
      y += 5;
      doc.setDrawColor(0);
      doc.line(margin, y, pageWidth - margin, y);
      y += 2;
    }

    // "No." column
    doc.setFontSize(12);
    doc.text(String(i + 1), margin + 5, y + rowHeight / 2, { baseline: 'middle' });

    // Image columns
    const imageY = y;
    doc.addImage(pair.before, 'PNG', margin + colWidth, imageY, imageWidth, imageHeight);
    doc.addImage(pair.after, 'PNG', margin + colWidth * 2, imageY, imageWidth, imageHeight);
    doc.addImage(pair.diff, 'PNG', margin + colWidth * 3, imageY, imageWidth, imageHeight);
    
    y += rowHeight;
    doc.setDrawColor(200);
    doc.line(margin, y, pageWidth - margin, y);
    y += 2;
  }

  doc.save('part-comparison-report.pdf');
};

const removePair = (id) => {
    croppedPairs.value = croppedPairs.value.filter(p => p.id !== id);
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

onMounted(() => { window.addEventListener('resize', redrawAllCanvases); });
onBeforeUnmount(() => { window.removeEventListener('resize', redrawAllCanvases); });
</script>

