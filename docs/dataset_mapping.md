| GTSRB ID | GTSRB Name | Internal Label (`class_labels.txt`) | Vietnamese Name | Reason for Selection |
|----------|------------|--------------------------------------|-----------------|---------------------|
| 40 | Roundabout mandatory | `bung_binh` | Vòng xuyến | Common intersection control |
| 17 | No entry | `cam_di_vao` | Cấm đi vào | Critical restriction sign |
| 35 | Ahead only | `chi_di_thang` | Chỉ đi thẳng | Frequent directional control |
| 25 | Road work | `dang_thi_cong` | Đường đang thi công | High real-world frequency |
| 38 | Keep right | `di_ben_phai` | Đi bên phải | Lane discipline |
| 39 | Keep left | `di_ben_trai` | Đi bên trái | Lane discipline |
| 14 | Stop | `dung` | Dừng | Safety-critical sign |
| 41 | End of no passing | `het_han_che` | Hết hạn chế | Regulation transition |
| 31 | Pedestrians | `nguoi_di_bo` | Người đi bộ qua đường | Urban safety sign |
| 33 | Turn right ahead | `re_phai` | Rẽ phải | Directional guidance |
| 34 | Turn left ahead | `re_trai` | Rẽ trái | Directional guidance |
| 0 | Speed limit (20km/h) | `toc_do_20` | Tốc độ tối đa 20 | School/low-speed zones |
| 1 | Speed limit (30km/h) | `toc_do_30` | Tốc độ tối đa 30 | Urban/residential roads |
| 2 | Speed limit (50km/h) | `toc_do_50` | Tốc độ tối đa 50 | Main urban roads |
| 28 | Children crossing | `tre_em_qua_duong` | Trẻ em qua đường | School zones |

## Selection Criteria

1. **High image count in GTSRB**: All selected classes have >500 images for robust training
2. **Relevance to Vietnamese traffic**: Prioritized signs common in Vietnam urban/rural areas
3. **Safety priority**: Included critical signs (Stop, No Entry, Speed Limits)
4. **Diversity**: Mix of regulatory (speed limits), warning (road work, children), and directional signs
5. **Shape variety**: Circular (speed limits), octagonal (stop), triangular (warnings), rectangular (directional)

## Implementation Notes

- **Image count per class**: Target 200 images per class (3,000 total)
- **GTSRB format**: PPM images, will convert to JPEG 96×96 for Edge Impulse
- **Class balance**: Stratified sampling ensures equal representation
- **Vietnamese naming**: Use Vietnamese labels for real-world deployment
