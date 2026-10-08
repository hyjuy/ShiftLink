# Equipment CNN dataset — 2026-10-08

8,951 retained PNG photographs (1280 x 720), six equipment classes and ten installed equipment instances.
Train: 7,178; validation: 893; test: 880. Whole equipment: 6,092; characteristic close views: 2,859.
Every equipment instance retains all twelve direction sectors. Five real lighting profiles include 1,791 dim photographs.

Extract the single equipment-cnn-20261008.zip into a dataset directory. Its train/val/test folders contain class subfolders HPU/PDP/CAU/GR/RT/CV and can be used by CNN ImageFolder loaders.
manifest.jsonl records labels, split, image SHA256, capture ID and scene/session grouping. metadata/ contains retained camera/lighting/feature records.

Originally captured 6,000 photographs, then added 3,600 photographs without replacing existing valid images.
Quality selection rejected 649 candidates; those originals and dataset copies were deleted at the user's request. No rejected image or its original metadata is included in this ZIP. Exclusion reasons remain as records.
Independent sampled visual reviews retained seven identifiable boundary cases, including six dark CAU photographs. Brightness alone is not a rejection criterion.

Human camera heights and standable floor/platform positions are used in the enlarged capture factory. Images are Unity renders of the current equipment models, not physical camera photographs. Existing equipment/background correlations remain; these data have not been used to measure CNN accuracy. Direction ranges are relaxed within a sector where equipment connections prevent a standing position; metadata records angle_range_relaxed.

Google Drive destination: https://drive.google.com/drive/folders/1CxBqCGu8sweYRiwg3DbIQAxNqONbPhBm?usp=drive_link
Use the accompanying SHA256SUMS to verify the archive after download.

Upload status: pending. The connected Drive upload tool rejects files above 512 MiB; this complete ZIP is 2,604,665,998 bytes. Upload the single ZIP through the Drive website to the folder above. The archive was verified locally; SHA256SUMS and packages.json record its exact hash and size.
