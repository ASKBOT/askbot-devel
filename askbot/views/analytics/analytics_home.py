from django.shortcuts import render

def analytics_index(request):
    """analytics home page"""
    return render(request, 'analytics/index.html')

