from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, EmailOTP
from .forms import UserCreationForm, UserChangeForm


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
	add_form = UserCreationForm
	form = UserChangeForm
	model = User
	list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
	list_filter = ('is_staff', 'is_active')
	ordering = ('email',)
	search_fields = ('email', 'first_name', 'last_name')

	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		(_('Personal info'), {'fields': ('first_name', 'last_name')}),
		(_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
		(_('Important dates'), {'fields': ('last_login', 'date_joined')}),
	)

	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active')
		}),
	)


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
	list_display = ('user', 'code', 'created_at', 'is_used')
	list_filter = ('is_used',)
	search_fields = ('user__email', 'code')

