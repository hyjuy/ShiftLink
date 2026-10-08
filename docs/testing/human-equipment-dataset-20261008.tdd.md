# Human equipment dataset validation — 2026-10-08

Completed 6,000 original photographs and 3,600 additions across all ten equipment instances.
Final quality selection: 8,951 retained, 649 excluded. Train 7,178 / val 893 / test 880.
Whole equipment 6,092 / characteristic close views 2,859; dim profile 1,791.
Every equipment retains twelve direction sectors. Actual floor/platform camera height is 1.2–1.8m, with standing-space collision checks in the enlarged 66×51m capture factory.

## RED checkpoints

- 2a46af0: previous camera height 2.3175203800201416 detected.
- cbc5a0e: human viewpoint and physical lighting metadata requirements fail.
- b08b3ca: CNN target label requirement fails for a larger neighboring object.
- 5ba49b3: twelve directions and characteristic close-view requirements fail.
- 3d4415f: missing quality selection module fails.

## GREEN checks

38 relevant unit tests pass, using python -B -m unittest discover -s tests -p <pattern>:

| Pattern | Tests |
|---|---:|
| test_unity_dataset.py | 11 |
| test_human_captures.py | 9 |
| test_unity_cls_target.py | 4 |
| test_augment_equipment_dataset.py | 4 |
| test_equipment_photo_quality.py | 6 |
| test_package_equipment_cnn.py | 1 |
| test_retire_excluded_photos.py | 3 |

Unity rendered and exported all 6,000 originals and all 3,600 additions successfully.
The merge validated PNG structure, CRC, dimensions, labels, unique image SHA256, split grouping, target-class CNN copies and byte preservation of all 6,000 originals before quality deletion.
Independent sampled visual reviews identified featureless plates, occluded targets and distant equipment; a final review preserved six identifiable dark CAU images and one RT boundary case.

At the user's final request, all 649 excluded originals and their capture/YOLO/CNN copies, associated JSON and labels were deleted: 6,490 files. Hashes, exact paths, metadata IDs and inventories were validated before the first unlink. Tests confirm a mismatching hash or malformed inventory aborts before deletion.
Final verification checks every retained hash, no excluded PNG in the three dataset runs, all six classes in each split and twelve directions for all ten equipment instances.
Packaging rereads every archived PNG and metadata record to verify SHA256 and capture ID. Only retained images and metadata are archived, with exclusion reason records but no excluded pixels.

The older 2026-10-07 capture/train/test photo sets were deleted during replacement. Current valid original photos were retained and supplemented.
git diff --check passes in the isolated PR worktree. Dataset PNGs and the complete ZIP are not committed to Git; small representative previews and records are included.
See [final records](equipment-dataset-20261008/README.md).

## Limits

These are Unity renders, not physical camera photographs. No CNN training or accuracy measurement was performed. Reviews are sampled plus specific repeated problem groups, not exhaustive visual inspection. Equipment/background correlations remain. When connections block preferred split-angle ranges, capture stays in the same sector and records angle_range_relaxed.
Python stdlib trace recorded executed paths; numeric coverage for all final changes and C# was not measured.
