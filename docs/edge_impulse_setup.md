# Edge Impulse Setup Guide

This guide walks through setting up Edge Impulse for training a traffic sign recognition model for ESP32-CAM.

## Prerequisites

- Edge Impulse account (free): https://studio.edgeimpulse.com/signup
- Dataset prepared using scripts (train and test folders)
- Stable internet connection

## Step 1: Create New Project (5 min)

1. Go to https://studio.edgeimpulse.com
2. Click "Create new project"
3. Project name: **Traffic Sign Recognition ESP32**
4. Project type: **Images**
5. Target device: **ESP32** (select from dropdown)

## Step 2: Upload Training Data (10-15 min)

1. Navigate to **Data acquisition** tab
2. Click **Upload data**
3. Select **Choose files**
4. Navigate to `D:\DoAn_Robot\data\train\`
5. Upload all folders (15 classes)
   - Edge Impulse auto-detects labels from folder names
   - Progress bar shows upload status
6. Wait for upload to complete (~2,400 images)

**Verify:**
- Data acquisition shows ~2,400 samples
- 15 labels visible in label distribution chart
- Each class has ~160 samples

## Step 3: Upload Test Data (5 min)

1. In **Data acquisition**, click **Upload data** again
2. Select **Choose files**
3. Navigate to `D:\DoAn_Robot\data\test\`
4. Upload all folders
5. **IMPORTANT:** Check "Automatically split between train and test" → Set to **Test data only**
6. Wait for upload (~600 images)

**Verify:**
- Test data shows ~600 samples
- Train/test split approximately 80/20
- All 15 labels present in test set

## Step 4: Create Impulse (10 min)

1. Navigate to **Create impulse** tab
2. Configure:

   **Image data:**
   - Image width: **96 px**
   - Image height: **96 px**
   - Resize mode: **Squash**

   **Processing block:**
   - Add **Image** block

   **Learning block:**
   - Add **Transfer Learning (Images)**

3. Click **Save Impulse**

## Step 5: Generate Features (5 min)

1. Navigate to **Image** tab (under Impulse design)
2. Configure:
   - Color depth: **RGB**
   - Auto balance dataset: **Enabled** (optional)
3. Click **Save parameters**
4. Click **Generate features**
5. Wait 3-5 minutes for feature extraction

**Verify:**
- Feature explorer shows 15 distinct clusters
- No major overlap between classes
- 2D/3D visualization shows class separation

## Step 6: Train Model (20-30 min)

1. Navigate to **Transfer Learning** tab
2. Configure neural network:

   **Model:**
   - Base model: **MobileNetV2 0.35** (smallest, fastest)
   - Transfer learning: **Enabled**

   **Training settings:**
   - Number of training cycles: **50** epochs
   - Learning rate: **0.001**
   - Batch size: **32** (auto)
   - Minimum confidence rating: **0.6**

   **Data augmentation:**
   - Enable augmentation: **✓**
   - Flip: **Horizontal only**
   - Rotation: **±15 degrees**
   - Crop: **10%**
   - Brightness: **±10%**

3. Click **Start training**
4. Wait 15-20 minutes (cloud GPU)

**Monitor:**
- Training accuracy should increase to >95%
- Validation accuracy target: >90% (ideally 92%+)
- Loss should decrease steadily

**If accuracy <90%:**
- Increase epochs to 80
- Reduce learning rate to 0.0005
- Enable more aggressive augmentation
- Retrain

## Step 7: Evaluate Model

1. Navigate to **Model testing** tab
2. Click **Classify all**
3. Wait for test results

**Target metrics:**
- Overall accuracy: **>90%**
- Precision: **>90%**
- Recall: **>90%**
- F1-score: **>90%**

**Review confusion matrix:**
- Identify misclassified pairs
- Check if specific signs are confused
- Document for improvement in Phase 6

## Step 8: Optimize and Deploy (15 min)

1. Navigate to **Deployment** tab
2. Select **Arduino library**
3. Configure optimization:

   **Enable EON Compiler:** ✓
   - Optimizes for embedded devices
   - Reduces model size
   - Speeds up inference

   **Enable int8 quantization:** ✓
   - Reduces size from ~1.2MB to ~350KB
   - Minor accuracy drop (<2%)
   - 3× faster on ESP32

4. Click **Build**
5. Wait 2-3 minutes for optimization

**Review model stats:**
- **Flash usage:** <500KB (target ~350KB)
- **RAM usage:** <200KB (ESP32 has 520KB)
- **Inference time:** <500ms at 320MHz

6. Click **Download** to get `.zip` file (~2MB with examples)

## Step 9: Extract and Verify Library

1. Download completes: `ei-traffic-sign-recognition-esp32-arduino-1.0.x.zip`
2. Extract to: `D:\DoAn_Robot\libraries\`
3. Verify contents:
   - `src/model-parameters/` - Model files
   - `src/edge-impulse-sdk/` - SDK files
   - `examples/` - Example sketches
   - `model_metadata.h` - Class labels, input size

**Model file size check:**
- Locate `src/tflite-model/trained_model_compiled.cpp`
- Should be ~350KB (if compressed)

## Step 10: Document Training Results

1. Navigate to **Dashboard** tab
2. Take screenshots:
   - Training curves (accuracy/loss)
   - Confusion matrix
   - Feature explorer
   - Model performance stats

3. Export project data:
   - **Dashboard → Project info → Clone project data**
   - Save project URL for reference: `https://studio.edgeimpulse.com/studio/{project-id}`

4. Note hyperparameters:
   - Epochs used
   - Learning rate
   - Augmentation settings
   - Final accuracy achieved

5. Create backup:
   - Download dataset: **Data acquisition → Export**
   - Download model: Already done in Step 8
   - Save screenshots to `D:\DoAn_Robot\docs\training_results\`

## Troubleshooting

### Upload fails
- Check internet stability
- Try uploading in smaller batches (5 classes at a time)
- Verify JPEG format (not PPM)

### Low accuracy (<85%)
- Increase training epochs to 80-100
- Enable more data augmentation
- Check class balance (all classes ~equal samples)
- Try MobileNetV2 0.5 (larger model)

### Model too large (>500KB)
- Use MobileNetV2 0.2 instead of 0.35
- Reduce image size to 64×64 (may hurt accuracy)
- Ensure int8 quantization is enabled

### Confusion between similar signs
- Add more training data for confused classes
- Increase augmentation for similar classes
- Consider merging very similar classes

## Next Steps

After completing Edge Impulse setup:
1. Proceed to **Phase 2: Hardware Assembly**
2. Install Arduino IDE and ESP32 board support
3. Test model with Phase 3 deployment script
4. Document training report in `docs/training_report.md`

## Free Tier Limits

Edge Impulse free tier provides:
- ✓ 1 active project
- ✓ Unlimited training hours
- ✓ Public projects only
- ✓ Community support
- ✗ No on-device debugging

**For this project:** Free tier is sufficient. No credit card required.
