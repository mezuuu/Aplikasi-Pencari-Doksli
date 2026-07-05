from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_alter_searchquery_search_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='originaldocument',
            name='image_data',
            field=models.TextField(
                blank=True,
                help_text='Base64 image data fallback for deployments without persistent media storage',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='originaldocument',
            name='image_mime_type',
            field=models.CharField(
                default='image/jpeg',
                help_text='MIME type for image_data',
                max_length=100,
            ),
        ),
    ]
