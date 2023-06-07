# Generated by Django 4.2.1 on 2023-06-07 02:16

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "nickname",
                    models.CharField(max_length=100, unique=True, verbose_name="닉네임"),
                ),
                (
                    "email",
                    models.EmailField(
                        max_length=100, unique=True, verbose_name="이메일 주소"
                    ),
                ),
                ("username", models.CharField(max_length=20, verbose_name="이름")),
                ("password", models.CharField(max_length=128, verbose_name="비밀 번호")),
                (
                    "join_date",
                    models.DateTimeField(auto_now_add=True, verbose_name="가입일"),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("is_admin", models.BooleanField(default=False)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Group",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
        ),
    ]