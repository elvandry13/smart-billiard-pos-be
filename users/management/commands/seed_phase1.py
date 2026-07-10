"""
Management command untuk membuat minimal seed data Phase 1 frontend.

Credential/password tidak disimpan di repository. Command ini hanya membaca
password dari environment variable lokal.

Usage:
    python manage.py seed_phase1
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import Outlet, Role, Tenant, User


class Command(BaseCommand):
    help = (
        'Seed minimal Phase 1: 1 tenant aktif, 1 outlet aktif, dan 4 user aktif '
        '(super_admin, owner, admin, officer). Password wajib dari environment.'
    )

    role_password_envs = {
        User.RoleEnum.SUPER_ADMIN: 'PHASE1_SUPER_ADMIN_PASSWORD',
        User.RoleEnum.OWNER: 'PHASE1_OWNER_PASSWORD',
        User.RoleEnum.ADMIN: 'PHASE1_ADMIN_PASSWORD',
        User.RoleEnum.OFFICER: 'PHASE1_OFFICER_PASSWORD',
    }

    role_username_envs = {
        User.RoleEnum.SUPER_ADMIN: ('PHASE1_SUPER_ADMIN_USERNAME', 'phase1_super_admin'),
        User.RoleEnum.OWNER: ('PHASE1_OWNER_USERNAME', 'phase1_owner'),
        User.RoleEnum.ADMIN: ('PHASE1_ADMIN_USERNAME', 'phase1_admin'),
        User.RoleEnum.OFFICER: ('PHASE1_OFFICER_USERNAME', 'phase1_officer'),
    }

    role_email_envs = {
        User.RoleEnum.SUPER_ADMIN: ('PHASE1_SUPER_ADMIN_EMAIL', 'phase1_super_admin@example.com'),
        User.RoleEnum.OWNER: ('PHASE1_OWNER_EMAIL', 'phase1_owner@example.com'),
        User.RoleEnum.ADMIN: ('PHASE1_ADMIN_EMAIL', 'phase1_admin@example.com'),
        User.RoleEnum.OFFICER: ('PHASE1_OFFICER_EMAIL', 'phase1_officer@example.com'),
    }

    def handle(self, *args, **options):
        self._validate_required_roles()
        passwords = self._get_passwords_from_env()

        with transaction.atomic():
            tenant = self._seed_tenant()
            outlet = self._seed_outlet(tenant)
            users = self._seed_users(tenant=tenant, outlet=outlet, passwords=passwords)

        self.stdout.write(self.style.SUCCESS('Seed Phase 1 berhasil dibuat/diperbarui.'))
        self.stdout.write(f'  Tenant: {tenant.name} ({tenant.code})')
        self.stdout.write(f'  Outlet: {outlet.name} ({outlet.code})')
        self.stdout.write('  Users:')
        for user in users:
            self.stdout.write(f'    - {user.username} [{user.role}]')
        self.stdout.write(self.style.WARNING('  [!] Password tidak dicetak. Simpan credential hanya di env lokal/password manager.'))

    def _validate_required_roles(self):
        required_roles = [choice.value for choice in User.RoleEnum]
        existing_roles = set(Role.objects.filter(name__in=required_roles).values_list('name', flat=True))
        missing_roles = sorted(set(required_roles) - existing_roles)

        if missing_roles:
            raise CommandError(
                'Role seed belum lengkap: '
                f'{", ".join(missing_roles)}. Jalankan migrasi terlebih dahulu: python manage.py migrate'
            )

    def _get_passwords_from_env(self):
        passwords = {}
        missing_envs = []

        for role, env_name in self.role_password_envs.items():
            password = os.environ.get(env_name)
            if not password:
                missing_envs.append(env_name)
            else:
                passwords[role] = password

        if missing_envs:
            raise CommandError(
                'Environment variable password Phase 1 belum lengkap: '
                f'{", ".join(missing_envs)}. Jangan commit credential; simpan di .env lokal/password manager.'
            )

        return passwords

    def _seed_tenant(self):
        tenant_code = os.environ.get('PHASE1_TENANT_CODE', 'PHASE1')
        tenant_name = os.environ.get('PHASE1_TENANT_NAME', 'Phase 1 Tenant')

        tenant, _created = Tenant.objects.update_or_create(
            code=tenant_code,
            defaults={
                'name': tenant_name,
                'is_active': True,
            },
        )
        return tenant

    def _seed_outlet(self, tenant):
        outlet_code = os.environ.get('PHASE1_OUTLET_CODE', 'P1O1')
        outlet_name = os.environ.get('PHASE1_OUTLET_NAME', 'Phase 1 Outlet')
        outlet_address = os.environ.get('PHASE1_OUTLET_ADDRESS', '')
        outlet_timezone = os.environ.get('PHASE1_OUTLET_TIMEZONE', 'Asia/Jakarta')

        outlet, _created = Outlet.objects.update_or_create(
            tenant=tenant,
            code=outlet_code,
            defaults={
                'name': outlet_name,
                'address': outlet_address,
                'timezone': outlet_timezone,
                'is_active': True,
            },
        )
        return outlet

    def _seed_users(self, tenant, outlet, passwords):
        users = []
        role_context = {
            User.RoleEnum.SUPER_ADMIN: {
                'tenant': None,
                'outlet': None,
                'is_staff': True,
                'is_superuser': True,
            },
            User.RoleEnum.OWNER: {
                'tenant': tenant,
                'outlet': None,
                'is_staff': False,
                'is_superuser': False,
            },
            User.RoleEnum.ADMIN: {
                'tenant': tenant,
                'outlet': outlet,
                'is_staff': False,
                'is_superuser': False,
            },
            User.RoleEnum.OFFICER: {
                'tenant': tenant,
                'outlet': outlet,
                'is_staff': False,
                'is_superuser': False,
            },
        }

        for role in User.RoleEnum:
            username_env, default_username = self.role_username_envs[role]
            email_env, default_email = self.role_email_envs[role]
            username = os.environ.get(username_env, default_username)
            email = os.environ.get(email_env, default_email)
            phone = os.environ.get(f'PHASE1_{role.upper()}_PHONE', '')

            user, _created = User.objects.get_or_create(username=username)
            user.email = email
            user.phone = phone
            user.role = role
            user.tenant = role_context[role]['tenant']
            user.outlet = role_context[role]['outlet']
            user.is_staff = role_context[role]['is_staff']
            user.is_superuser = role_context[role]['is_superuser']
            user.is_active = True
            user.set_password(passwords[role])
            user.save()

            users.append(user)

        return users