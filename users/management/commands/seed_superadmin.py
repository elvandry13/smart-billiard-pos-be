"""
Management command untuk membuat akun Super Admin pertama kali.
Usage: python manage.py seed_superadmin
"""
import os
from django.core.management.base import BaseCommand
from users.models import User, Role


class Command(BaseCommand):
    help = 'Seed Super Admin user pertama kali (idempoten — hanya dibuat jika belum ada)'

    def handle(self, *args, **options):
        username = os.environ.get('SUPER_ADMIN_USERNAME', 'superadmin')
        email = os.environ.get('SUPER_ADMIN_EMAIL', 'superadmin@example.com')
        password = os.environ.get('SUPER_ADMIN_PASSWORD')
        phone = os.environ.get('SUPER_ADMIN_PHONE', '')

        if not password:
            self.stderr.write(self.style.ERROR('SUPER_ADMIN_PASSWORD environment variable tidak ditemukan.'))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'Super Admin "{username}" sudah ada, dilewati.'))
            return

        super_admin = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            phone=phone,
            role=User.RoleEnum.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        # Assign super_admin Role
        try:
            role = Role.objects.get(name='super_admin')
            super_admin.roles.add(role)
        except Role.DoesNotExist:
            self.stdout.write(self.style.WARNING('Role "super_admin" tidak ditemukan — pastikan migrasi sudah dijalankan.'))

        self.stdout.write(self.style.SUCCESS(f'Super Admin "{username}" berhasil dibuat!'))
        self.stdout.write(f'  Username: {username}')
        self.stdout.write(self.style.WARNING('  [!] Harap ganti password setelah login pertama!'))
