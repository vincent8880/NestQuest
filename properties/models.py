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
    detail_url = models.URLField(blank=True, null=True)
    listing_url = models.URLField(blank=True, null=True)
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
    url = models.URLField()  # URL to image on Property24
    is_thumbnail = models.BooleanField(default=False)  # Only one image per property is thumbnail
    # Identity & ordering
    image_base_id = models.CharField(max_length=64, blank=True, null=True)
    variant = models.CharField(max_length=64, blank=True, null=True)
    order_index = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Image for {self.property.title}"
    
    class Meta:
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
