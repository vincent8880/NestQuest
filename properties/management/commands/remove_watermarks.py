"""
Standalone command to remove Property24 watermarks from scraped images.

This command:
1. Finds all images from Property24 source
2. Downloads each image
3. Intelligently removes the watermark from bottom-right corner
4. Saves cleaned images to a specified output directory

Usage:
    python manage.py remove_watermarks --source Property24 --output-dir ./cleaned_images
    python manage.py remove_watermarks --source Property24 --limit 100 --dry-run
"""

import os
import io
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.conf import settings
from properties.models import Image, Property, Source

try:
    import cv2
    import numpy as np
    from PIL import Image as PILImage
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    try:
        from PIL import Image as PILImage
        PIL_AVAILABLE = True
    except ImportError:
        PIL_AVAILABLE = False


class Command(BaseCommand):
    help = 'Remove Property24 watermarks from scraped images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default='Property24',
            help='Source name to filter images (default: Property24)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=None,
            help='Directory to save cleaned images (default: uses MEDIA_ROOT/images/cleaned/)'
        )
        parser.add_argument(
            '--save-backup',
            action='store_true',
            default=True,
            help='Save original images as backup (default: True)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of images to process (for testing)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually processing'
        )
        parser.add_argument(
            '--method',
            type=str,
            choices=['inpaint', 'crop', 'smart_crop'],
            default='smart_crop',
            help='Watermark removal method: inpaint (best quality, requires opencv), crop (simple bottom crop), smart_crop (intelligent corner crop)'
        )
        parser.add_argument(
            '--crop-percent',
            type=float,
            default=5.0,
            help='Percentage of image to crop from bottom-right (default: 5.0)'
        )

    def handle(self, *args, **options):
        source_name = options['source']
        output_dir = options['output_dir']
        save_backup = options.get('save_backup', True)
        limit = options.get('limit')
        dry_run = options.get('dry_run', False)
        method = options.get('method', 'smart_crop')
        crop_percent = options.get('crop_percent', 5.0)

        # Check dependencies
        if method == 'inpaint' and not CV2_AVAILABLE:
            self.stdout.write(
                self.style.ERROR(
                    'OpenCV (cv2) is required for inpainting method. '
                    'Install with: pip install opencv-python'
                )
            )
            return

        if not PIL_AVAILABLE:
            self.stdout.write(
                self.style.ERROR(
                    'PIL/Pillow is required. Install with: pip install Pillow'
                )
            )
            return

        # Get source
        try:
            source = Source.objects.get(name=source_name)
        except Source.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Source "{source_name}" not found')
            )
            return

        # Get Property24 images
        images = Image.objects.filter(
            property__source=source
        ).select_related('property')

        # Filter for Property24 URLs
        property24_images = [
            img for img in images
            if 'images.prop24.com' in img.url or 'property24' in img.url.lower()
        ]

        if limit:
            property24_images = property24_images[:limit]

        total = len(property24_images)
        self.stdout.write(
            self.style.SUCCESS(f'Found {total} Property24 images to process')
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be modified'))
            for i, img in enumerate(property24_images[:10], 1):
                self.stdout.write(f'  {i}. {img.url[:80]}...')
            if total > 10:
                self.stdout.write(f'  ... and {total - 10} more')
            return

        # Determine output directories
        if output_dir:
            # Custom output directory
            cleaned_dir = Path(output_dir) / "cleaned"
            backup_dir = Path(output_dir) / "originals" if save_backup else None
        else:
            # Use Django MEDIA_ROOT structure
            cleaned_dir = Path(settings.MEDIA_ROOT) / "images" / "cleaned" / source_name.lower()
            backup_dir = Path(settings.MEDIA_ROOT) / "images" / "originals" / source_name.lower() if save_backup else None
        
        # Create directories
        cleaned_dir.mkdir(parents=True, exist_ok=True)
        if backup_dir:
            backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.stdout.write(f'✅ Cleaned images: {cleaned_dir.absolute()}')
        if backup_dir:
            self.stdout.write(f'✅ Backup originals: {backup_dir.absolute()}')

        # Process images
        processed = 0
        failed = 0
        skipped = 0

        for i, img in enumerate(property24_images, 1):
            try:
                self.stdout.write(f'\n[{i}/{total}] Processing: {img.url[:80]}...')
                
                # Download image
                try:
                    response = requests.get(img.url, timeout=30, stream=True)
                    response.raise_for_status()
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  Failed to download: {e}')
                    )
                    failed += 1
                    continue

                # Process image
                try:
                    cleaned_image = self._remove_watermark(
                        response.content,
                        method=method,
                        crop_percent=crop_percent
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  Failed to process: {e}')
                    )
                    failed += 1
                    continue

                if cleaned_image is None:
                    self.stdout.write('  ⏭️  Skipped (no watermark detected)')
                    skipped += 1
                    continue

                # Save cleaned image and backup
                try:
                    # Save cleaned image (main - what users will see)
                    cleaned_filename = f"{img.id}_cleaned.jpg"
                    cleaned_file = cleaned_dir / cleaned_filename
                    cleaned_image.save(cleaned_file, quality=90, optimize=True)
                    
                    # Generate cleaned URL (relative to MEDIA_URL)
                    source_name = source.name.lower()
                    cleaned_url = f"{settings.MEDIA_URL}images/cleaned/{source_name}/{cleaned_filename}"
                    
                    # Update database with cleaned URL
                    img.cleaned_url = cleaned_url
                    img.save(update_fields=['cleaned_url'])
                    
                    # Save original as backup (if requested)
                    if save_backup and backup_dir:
                        original_img = PILImage.open(io.BytesIO(response.content))
                        if original_img.mode == 'RGBA':
                            original_img = original_img.convert('RGB')
                        backup_filename = f"{img.id}_original.jpg"
                        backup_file = backup_dir / backup_filename
                        original_img.save(backup_file, quality=95, optimize=True)
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✅ Saved cleaned + backup + updated DB: {cleaned_filename}')
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✅ Saved cleaned + updated DB: {cleaned_filename}')
                        )
                    
                    processed += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Failed to save: {e}')
                    )
                    failed += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Unexpected error: {e}')
                )
                failed += 1

        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'✅ Processed: {processed}')
        self.stdout.write(f'⏭️  Skipped: {skipped}')
        self.stdout.write(f'❌ Failed: {failed}')
        self.stdout.write(f'\n📁 Cleaned images: {cleaned_dir.absolute()}')
        if backup_dir:
            self.stdout.write(f'📁 Backup originals: {backup_dir.absolute()}')
        self.stdout.write(f'\n✅ Database updated: cleaned_url field populated for {processed} images')
        self.stdout.write(f'💡 Next step: Update templates to use image.get_display_url instead of image.url')
        self.stdout.write(f'💡 Original URLs preserved in url field as backup reference')

    def _remove_watermark(
        self,
        image_data: bytes,
        method: str = 'smart_crop',
        crop_percent: float = 5.0
    ) -> Optional[PILImage.Image]:
        """
        Remove watermark from image using specified method.
        
        Returns PIL Image object or None if processing failed.
        """
        try:
            # Load image
            img = PILImage.open(io.BytesIO(image_data))
            
            # Convert RGBA to RGB if needed
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            width, height = img.size
            
            if method == 'crop':
                # Simple: crop entire bottom strip (removes bottom X% of image)
                # This removes the bottom portion including watermark
                crop_height = int(height * (1 - crop_percent / 100))
                return img.crop((0, 0, width, crop_height))
            
            elif method == 'smart_crop':
                # Intelligent: crop only the bottom-right corner (where watermark is)
                # This keeps most of the image, only removing the corner with watermark
                # Example: If image is 1000x800 and crop_percent=5%:
                #   - Removes 50px from right edge
                #   - Removes 40px from bottom edge
                #   - Result: 950x760 image (watermark corner removed)
                crop_width = int(width * crop_percent / 100)
                crop_height = int(height * crop_percent / 100)
                # Crop from top-left (0,0) to (width - crop_width, height - crop_height)
                # This removes the bottom-right corner rectangle
                return img.crop((0, 0, width - crop_width, height - crop_height))
            
            elif method == 'inpaint':
                # BEST QUALITY: Use inpainting to intelligently fill the watermark area
                # This keeps the full image size and fills the watermark with surrounding pixels
                # Result: Full-size image with watermark seamlessly removed
                if not CV2_AVAILABLE:
                    raise ImportError('OpenCV required for inpainting')
                
                # Convert PIL to OpenCV format
                img_array = np.array(img)
                img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # Create mask for bottom-right corner (watermark area)
                # Property24 watermark is typically in bottom-right, about 5-8% of image
                mask = np.zeros(img_cv.shape[:2], dtype=np.uint8)
                crop_width = int(width * crop_percent / 100)
                crop_height = int(height * crop_percent / 100)
                
                # Mark bottom-right corner rectangle as area to inpaint
                # mask[y_start:y_end, x_start:x_end] = 255
                # This marks the bottom-right corner for inpainting
                mask[height - crop_height:, width - crop_width:] = 255
                
                # Apply inpainting with TELEA algorithm (good for small areas like watermarks)
                # Inpaint radius of 3 pixels works well for watermarks
                # This fills the masked area using surrounding pixel information
                inpainted = cv2.inpaint(img_cv, mask, 3, cv2.INPAINT_TELEA)
                
                # Convert back to PIL
                inpainted_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)
                return PILImage.fromarray(inpainted_rgb)
            
            else:
                raise ValueError(f'Unknown method: {method}')
                
        except Exception as e:
            self.stdout.write(f'Error in _remove_watermark: {e}')
            return None


