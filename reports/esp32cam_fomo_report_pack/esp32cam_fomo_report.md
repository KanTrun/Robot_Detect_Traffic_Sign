# ESP32-CAM FOMO Report Pack

**Model summary**
- Schema: `fomo-grid-v2`
- Model type: `fomo_grid_detector`
- Input shape: `[1, 96, 96, 3]`
- Output shape: `[1, 12, 12, 5]`
- Deploy header source: `traffic_sign_fomo_float32.tflite`
- Class labels: `_background_, stop, speed_limit, warning, other_reg`

**Dataset split**
- Train: `{'_background_': 480, 'stop': 480, 'speed_limit': 480, 'warning': 480, 'other_reg': 480}`
- Val: `{'_background_': 120, 'stop': 120, 'speed_limit': 120, 'warning': 120, 'other_reg': 120}`
- Test: `{'_background_': 120, 'stop': 120, 'speed_limit': 120, 'warning': 120, 'other_reg': 120}`

**Training**
- Final train loss: `0.0401`
- Final val loss: `0.0384`
- Final train sign-cell recall: `0.7368`
- Final val sign-cell recall: `0.5839`

**Canonical Eval (0.65)**
- `train`: overall `0.5996`, `print=0.5867`, `screen=0.6125`
- `val`: overall `0.5900`, `print=0.5900`, `screen=0.5900`
- `test`: overall `0.5433`, `print=0.5300`, `screen=0.5567`

**Strict Release Test Gate**
- Threshold: `0.7`
- Min votes: `2`
- `print` accuracy: `0.4833`
- `screen` accuracy: `0.5100`


**Test Per-Class Metrics: Print Domain**
| Label | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| _background_ | 60 | 0.418 | 0.633 | 0.503 |
| stop | 60 | 0.577 | 0.500 | 0.536 |
| speed_limit | 60 | 0.632 | 0.400 | 0.490 |
| warning | 60 | 0.590 | 0.383 | 0.465 |
| other_reg | 60 | 0.550 | 0.733 | 0.629 |

**Test Per-Class Metrics: Screen Domain**
| Label | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| _background_ | 60 | 0.350 | 0.600 | 0.442 |
| stop | 60 | 0.766 | 0.600 | 0.673 |
| speed_limit | 60 | 0.548 | 0.383 | 0.451 |
| warning | 60 | 0.727 | 0.400 | 0.516 |
| other_reg | 60 | 0.640 | 0.800 | 0.711 |

**Artifacts**
- `training_curves.png`
- `accuracy_by_split.png`
- `canonical_test_print_confusion.png`
- `canonical_test_screen_confusion.png`
- `strict_test_print_confusion.png`
- `strict_test_screen_confusion.png`
- `per_class_metrics.csv`

**Unresolved Questions**
- The current report is based on synthetic/full-frame bootstrapped data plus the current exported FOMO model. It does not yet include a separate hardware-only benchmark on a captured real-world ESP32-CAM evaluation set.
