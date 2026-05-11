import os
import shutil
import uuid
import hashlib
from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import OriginalDocument
from services.embedding_service import extract_embedding

def _compute_file_hash(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

class Command(BaseCommand):
    help = 'Bulk import Original Documents (Doksli) from a directory'

    def add_arguments(self, parser):
        parser.add_argument('directory', type=str, help='Path to directory containing images')

    def handle(self, *args, **kwargs):
        directory = kwargs['directory']
        
        if not os.path.exists(directory):
            self.stdout.write(self.style.ERROR(f'Directory does not exist: {directory}'))
            return
            
        media_dir = os.path.join(settings.MEDIA_ROOT, 'originals')
        os.makedirs(media_dir, exist_ok=True)
        
        supported_exts = ('.jpg', '.jpeg', '.png', '.webp')
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        self.stdout.write(f'Scanning directory: {directory}...')
        
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename.lower().endswith(supported_exts):
                    source_path = os.path.join(root, filename)
                    
                    try:
                        file_hash = _compute_file_hash(source_path)
                        
                        # Check duplicate
                        if OriginalDocument.objects.filter(file_hash=file_hash).exists():
                            self.stdout.write(self.style.WARNING(f'Skipped (Duplicate hash): {filename}'))
                            skip_count += 1
                            continue
                            
                        # Generate unique filename for storage
                        ext = os.path.splitext(filename)[1].lower()
                        new_filename = f"{uuid.uuid4().hex}{ext}"
                        dest_path = os.path.join(media_dir, new_filename)
                        
                        # Copy file
                        shutil.copy2(source_path, dest_path)
                        
                        # Extract embedding
                        self.stdout.write(f'Extracting embedding for {filename}...')
                        embedding = extract_embedding(dest_path)
                        
                        # Save to DB
                        OriginalDocument.objects.create(
                            image_path=dest_path,
                            embedding_vector=embedding,
                            file_hash=file_hash
                        )
                        
                        self.stdout.write(self.style.SUCCESS(f'Successfully imported: {filename}'))
                        success_count += 1
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Failed to import {filename}: {str(e)}'))
                        error_count += 1
                        
        self.stdout.write(self.style.SUCCESS(f'\nBulk import completed!'))
        self.stdout.write(f'Success: {success_count}')
        self.stdout.write(f'Skipped: {skip_count}')
        self.stdout.write(f'Errors : {error_count}')
        self.stdout.write(f'Total: {success_count + skip_count + error_count}')
