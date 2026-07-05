# Image processing safety validation

Validation scope:

- `posting.enable_images: false` stops non-dry-run processing before image scanning
- image URL attachment does not change `status: draft` to `ready`
- Python compilation
- full unit test suite
- repository validation
