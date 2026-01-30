| GTSRB ID | GTSRB Name | Vietnam Sign | Vietnamese Name | Reason for Selection |
|----------|------------|--------------|-----------------|---------------------|
| 0 | Speed limit (20km/h) | Speed Limit 20 | Tốc độ tối đa 20 | Common in school zones |
| 1 | Speed limit (30km/h) | Speed Limit 30 | Tốc độ tối đa 30 | Residential areas |
| 2 | Speed limit (50km/h) | Speed Limit 50 | Tốc độ tối đa 50 | Urban roads |
| 14 | Stop | Stop Sign | Dừng | Critical safety sign |
| 17 | No entry | No Entry | Cấm đi ngược chiều | Common traffic restriction |
| 25 | Road work | Road Work | Đường đang thi công | Frequent in Vietnam |
| 28 | Children crossing | Children Crossing | Trẻ em qua đường | School zones |
| 31 | Wild animals crossing | Pedestrian Crossing | Người đi bộ qua đường | Urban/rural areas |
| 33 | Turn right ahead | Turn Right | Rẽ phải phía trước | Directional guidance |
| 34 | Turn left ahead | Turn Left | Rẽ trái phía trước | Directional guidance |
| 35 | Ahead only | Straight Only | Chỉ được đi thẳng | Intersection control |
| 38 | Keep right | Keep Right | Chỉ được đi bên phải | Lane discipline |
| 39 | Keep left | Keep Left | Chỉ được đi bên trái | Lane discipline |
| 40 | Roundabout mandatory | Roundabout | Bắt buộc đi vòng | Intersection type |
| 41 | End of no passing | End Restriction | Hết khu vực cấm vượt | Speed zone change |

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
