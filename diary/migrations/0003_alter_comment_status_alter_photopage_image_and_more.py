# Generated by Django 4.2.1 on 2023-06-09 05:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0002_rename_cateogry_note_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comment",
            name="status",
            field=models.CharField(
                choices=[("0", "활성화"), ("1", "비활성화"), ("2", "강제중지"), ("3", "삭제")],
                default=0,
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="photopage",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to=""),
        ),
        migrations.AlterField(
            model_name="photopage",
            name="status",
            field=models.CharField(
                choices=[("0", "활성화"), ("1", "비활성화"), ("2", "강제중지"), ("3", "삭제")],
                default=0,
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="planpage",
            name="location",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="planpage",
            name="memo",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="planpage",
            name="status",
            field=models.CharField(
                choices=[("0", "활성화"), ("1", "비활성화"), ("2", "강제중지"), ("3", "삭제")],
                default=0,
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="planpage",
            name="time",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
