from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Property, Source, Image, Contact, PropertyDetail

def property_list(request):
    """Property listing page - Apartments.com style"""
    properties = Property.objects.prefetch_related('images', 'details').all().order_by('-created_at')
    
    # Apply filters
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    property_type = request.GET.get('type')
    location = request.GET.get('location')
    beds = request.GET.get('beds')
    
    if min_price:
        try:
            properties = properties.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            properties = properties.filter(price__lte=float(max_price))
        except ValueError:
            pass
    if property_type:
        properties = properties.filter(property_type=property_type)
    if location:
        properties = properties.filter(location__icontains=location)
    if beds:
        # Filter by bedrooms from PropertyDetail
        properties = properties.filter(details__key='bedrooms', details__value__gte=beds).distinct()
    
    # Pagination
    paginator = Paginator(properties, 20)  # 20 properties per page (like Apartments.com)
    page = request.GET.get('page')
    properties_page = paginator.get_page(page)
    
    context = {
        'properties': properties_page,
        'property_types': Property.objects.values_list('property_type', flat=True).distinct(),
        'locations': Property.objects.values_list('location', flat=True).distinct(),
        'total_count': properties.count()
    }
    return render(request, 'properties/property_list.html', context)

def property_detail(request, property_id):
    """Individual property detail page - Apartments.com style"""
    property_obj = get_object_or_404(
        Property.objects.prefetch_related('images', 'contacts', 'details'),
        id=property_id
    )
    
    # Get property details as dict
    details = {}
    for detail in property_obj.details.all():
        details[detail.key] = detail.value
    
    # Get all images ordered by order_index
    all_images = property_obj.images.all().order_by('order_index')
    thumbnail = all_images.filter(is_thumbnail=True).first() or all_images.first()
    gallery_images = [img for img in all_images if img != thumbnail]
    
    # Get contact information
    contacts = property_obj.contacts.all()
    
    # Helper: get detail value or None
    def get_detail(key):
        return details.get(key, None)
    
    context = {
        'property': property_obj,
        'details': details,
        'get_detail': get_detail,
        'thumbnail': thumbnail,
        'gallery_images': gallery_images,
        'all_images': all_images,
        'contacts': contacts,
        'beds': get_detail('bedrooms') or get_detail('beds'),
        'baths': get_detail('bathrooms') or get_detail('baths'),
        'parking': get_detail('parking') or get_detail('garages'),
        'floor_size': get_detail('floor_size') or get_detail('floor_area'),
        'description': get_detail('description'),
    }
    return render(request, 'properties/property_detail.html', context)

def search_properties(request):
    """AJAX search endpoint"""
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'results': []})
    
    properties = Property.objects.filter(
        Q(title__icontains=query) |
        Q(location__icontains=query) |
        Q(property_type__icontains=query)
    )[:10]  # Limit to 10 results
    
    results = [{
        'id': p.id,
        'title': p.title,
        'location': p.location,
        'price': float(p.price),
        'type': p.property_type
    } for p in properties]
    
    return JsonResponse({'results': results})
