from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.property_list, name='property_list'),
    path('property/<uuid:property_id>/', views.property_detail, name='property_detail'),
    path('search/', views.search_properties, name='search_properties'),
] 