import uuid
from django.db import models
from django.utils import timezone

class Source(models.Model):
    name = models.CharField(max_length=100, unique=True)  # e.g., "Property24"
    url = models.URLField()
    
    def __str__(self):
        return self.name

class Property(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='properties', null=True)
    external_id = models.CharField(max_length=100, blank=True, null=True)  # Property24's unique ID
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    location = models.CharField(max_length=255, default='Nairobi')  # e.g., "Nairobi, Westlands"
    property_type = models.CharField(max_length=50, default='other')  # e.g., "Apartment", "House"
    # Provenance & lifecycle
    # Increase URL max_length to safely store long tracking/query URLs (e.g. BuyRentKenya)
    detail_url = models.URLField(blank=True, null=True, max_length=500)
    listing_url = models.URLField(blank=True, null=True, max_length=500)
    listing_page = models.IntegerField(blank=True, null=True)
    card_index = models.IntegerField(blank=True, null=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_crawled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['source', 'external_id']
        verbose_name_plural = 'Properties'
    
    def __str__(self):
        return f"{self.title} - {self.location}"

class Image(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    url = models.URLField(max_length=500)  # Original URL (with watermark) - kept as backup reference
    cleaned_url = models.URLField(max_length=500, blank=True, null=True)  # Cleaned image URL (no watermark) - used for display
    is_thumbnail = models.BooleanField(default=False)  # Only one image per property is thumbnail
    # Identity & ordering
    image_base_id = models.CharField(max_length=64, blank=True, null=True)
    variant = models.CharField(max_length=64, blank=True, null=True)
    order_index = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Image for {self.property.title}"
    
    def get_display_url(self):
        """
        Returns cleaned image URL if available, otherwise original URL.
        Fast database lookup - no file system checks!
        """
        return self.cleaned_url if self.cleaned_url else self.url
    
    class Meta:
        ordering = ['order_index', 'id']  # Consistent ordering everywhere
        constraints = [
            models.UniqueConstraint(
                fields=['property'],
                condition=models.Q(is_thumbnail=True),
                name='unique_thumbnail_per_property'
            )
        ,
            models.UniqueConstraint(
                fields=['property', 'image_base_id', 'variant'],
                name='unique_image_variant_per_property'
            )
        ]

class Contact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    def __str__(self):
        return f"Contact for {self.property.title}: {self.name}"

class PropertyDetail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='details')
    key = models.CharField(max_length=100)  # e.g., "bedrooms", "bathrooms"
    value = models.CharField(max_length=2000)  # e.g., "3", "2", or longer descriptions
    
    class Meta:
        unique_together = ['property', 'key']
    
    def __str__(self):
        return f"{self.property.title} - {self.key}: {self.value}"

class ScrapingProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    area = models.CharField(max_length=100)  # e.g., "Karen", "Lavington"
    url_pattern = models.CharField(max_length=255)  # Property24's URL pattern for this area
    last_page_scraped = models.IntegerField(default=0)
    total_properties = models.IntegerField(default=0)
    last_scraped_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending')
    error_message = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = 'Scraping Progress'
    
    def __str__(self):
        return f"{self.area} - {self.status} (Page {self.last_page_scraped})"

class Visitor(models.Model):
    """Track website visitors and page views"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = models.GenericIPAddressField()
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10, default='GET')
    user_agent = models.CharField(max_length=200, blank=True)
    referer = models.URLField(max_length=500, blank=True)
    visited_at = models.DateTimeField(auto_now_add=True)
    is_login = models.BooleanField(default=False)  # True if this was a login action
    
    class Meta:
        ordering = ['-visited_at']
        indexes = [
            models.Index(fields=['-visited_at']),
            models.Index(fields=['ip_address', '-visited_at']),
            models.Index(fields=['user', '-visited_at']),
        ]
    
    def __str__(self):
        user_str = self.user.username if self.user else 'Anonymous'
        return f"{user_str} ({self.ip_address}) - {self.path} - {self.visited_at.strftime('%Y-%m-%d %H:%M')}"
