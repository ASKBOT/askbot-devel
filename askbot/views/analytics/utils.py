"""
Utilities for use in the analytics views
"""
from django.urls import reverse

def get_date_selector_url_func(view_name, **fixed_params):
    """
    Returns a function that will generate a URL for the given view name,
    with all parameters in fixed_params bound, except for the dates parameter.
    """
    def date_selector_url_func(dates):
        """
        Generates a URL with the given dates and all other parameters
        from the outer function.
        """
        params = fixed_params.copy()
        params['dates'] = dates
        return reverse(view_name, kwargs=params)
        
    return date_selector_url_func