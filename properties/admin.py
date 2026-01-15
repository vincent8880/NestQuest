from django.contrib import admin
from django.utils.html import format_html
from .models import Property, Source, Image, Contact, PropertyDetail, ScrapingProgress, Visitor

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'url']
    search_fields = ['name']

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['title', 'property_type', 'price', 'location', 'created_at']
    list_filter = ['property_type', 'created_at']
    search_fields = ['title', 'location', 'external_id']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ['property', 'url', 'is_thumbnail']
    list_filter = ['is_thumbnail']
    search_fields = ['property__title', 'url']

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['property', 'name', 'phone', 'email']
    search_fields = ['property__title', 'name', 'phone', 'email']

@admin.register(PropertyDetail)
class PropertyDetailAdmin(admin.ModelAdmin):
    list_display = ['property', 'key', 'value']
    list_filter = ['key']
    search_fields = ['property__title', 'key', 'value']

@admin.register(ScrapingProgress)
class ScrapingProgressAdmin(admin.ModelAdmin):
    list_display = ['area', 'status', 'last_page_scraped', 'total_properties', 'last_scraped_at']
    list_filter = ['status', 'area']
    search_fields = ['area']
    readonly_fields = ['last_scraped_at']

@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'user', 'path', 'method', 'is_login', 'visited_at']
    list_filter = ['is_login', 'method', 'visited_at', 'user']
    search_fields = ['ip_address', 'path', 'user__username']
    readonly_fields = ['visited_at']
    date_hierarchy = 'visited_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
