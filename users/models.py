from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from .managers import UserManager


class Tenant(models.Model):
    """Tenant/bisnis yang menjadi induk dari satu atau lebih outlet."""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Outlet(models.Model):
    """Cabang/outlet dalam satu tenant."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='outlets')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    address = models.TextField(blank=True, default='')
    timezone = models.CharField(max_length=50, default='Asia/Jakarta')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant', 'name']
        unique_together = ['tenant', 'code']

    def __str__(self):
        return f"{self.tenant.name} - {self.name}"


class Permission(models.Model):
    """Permission untuk aksi spesifik di aplikasi (bawaan Django custom)."""
    name = models.CharField(max_length=100, unique=True)
    codename = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['codename']

    def __str__(self):
        return self.name


class Role(models.Model):
    """Role user: super_admin, owner, admin, officer."""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model — semua user terdaftar di sini."""
    class RoleEnum(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        OWNER = 'owner', 'Owner'
        ADMIN = 'admin', 'Admin'
        OFFICER = 'officer', 'Officer'

    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    role = models.CharField(max_length=20, choices=RoleEnum.choices, default=RoleEnum.OFFICER)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name='users'
    )
    outlet = models.ForeignKey(
        Outlet, on_delete=models.SET_NULL, null=True, blank=True, related_name='users'
    )
    roles = models.ManyToManyField(Role, blank=True, related_name='users')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    objects = UserManager()

    class Meta:
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_super_admin(self):
        return self.role == self.RoleEnum.SUPER_ADMIN

    @property
    def is_owner(self):
        return self.role == self.RoleEnum.OWNER

    @property
    def is_admin(self):
        return self.role == self.RoleEnum.ADMIN

    @property
    def is_officer(self):
        return self.role == self.RoleEnum.OFFICER