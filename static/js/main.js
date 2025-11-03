// Main JavaScript for NestQuest

$(document).ready(function() {
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Smooth scrolling for anchor links
    $('a[href*="#"]').not('[href="#"]').not('[href="#0"]').click(function(event) {
        if (location.pathname.replace(/^\//, '') == this.pathname.replace(/^\//, '') && location.hostname == this.hostname) {
            var target = $(this.hash);
            target = target.length ? target : $('[name=' + this.hash.slice(1) + ']');
            if (target.length) {
                event.preventDefault();
                $('html, body').animate({
                    scrollTop: target.offset().top - 100
                }, 1000);
            }
        }
    });

    // Search suggestions functionality
    $('#search-input').on('input', function() {
        const query = $(this).val();
        if (query.length >= 2) {
            $.ajax({
                url: '/api/search-suggestions/',
                data: { 'q': query },
                success: function(data) {
                    displaySearchSuggestions(data.suggestions);
                }
            });
        } else {
            hideSearchSuggestions();
        }
    });

    function displaySearchSuggestions(suggestions) {
        const suggestionsContainer = $('#search-suggestions');
        suggestionsContainer.empty();
        
        if (suggestions.length > 0) {
            suggestions.forEach(function(suggestion) {
                const item = $(`
                    <div class="suggestion-item p-2 border-bottom" data-value="${suggestion.value}">
                        <i class="fas fa-${suggestion.type === 'location' ? 'map-marker-alt' : 'home'} me-2"></i>
                        ${suggestion.text}
                    </div>
                `);
                suggestionsContainer.append(item);
            });
            suggestionsContainer.show();
        } else {
            hideSearchSuggestions();
        }
    }

    function hideSearchSuggestions() {
        $('#search-suggestions').hide();
    }

    // Property save/unsave functionality
    $('.save-property-btn').click(function(e) {
        e.preventDefault();
        
        if (!isAuthenticated()) {
            window.location.href = '/accounts/login/';
            return;
        }

        const button = $(this);
        const propertyId = button.data('property-id');
        const icon = button.find('i');
        
        $.ajax({
            url: '/save-property/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            data: JSON.stringify({
                'property_id': propertyId
            }),
            success: function(data) {
                if (data.saved) {
                    icon.removeClass('far').addClass('fas');
                    button.removeClass('btn-outline-danger').addClass('btn-danger');
                    showToast('Property saved successfully!', 'success');
                } else {
                    icon.removeClass('fas').addClass('far');
                    button.removeClass('btn-danger').addClass('btn-outline-danger');
                    showToast('Property removed from saved list', 'info');
                }
            },
            error: function() {
                showToast('Error saving property. Please try again.', 'error');
            }
        });
    });

    // Filter form auto-submit
    $('.filter-form select, .filter-form input[type="range"]').change(function() {
        $(this).closest('form').submit();
    });

    // Price range slider
    if ($('#price-range').length) {
        const priceRange = document.getElementById('price-range');
        const priceDisplay = document.getElementById('price-display');
        
        priceRange.addEventListener('input', function() {
            priceDisplay.textContent = `R${parseInt(this.value).toLocaleString()}`;
        });
    }

    // Property image gallery
    $('.property-gallery img').click(function() {
        const src = $(this).attr('src');
        const modal = $(`
            <div class="modal fade" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-body p-0">
                            <img src="${src}" class="img-fluid w-100" alt="Property Image">
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        $('body').append(modal);
        modal.modal('show');
        
        modal.on('hidden.bs.modal', function() {
            modal.remove();
        });
    });

    // Infinite scroll for property listings (future feature)
    if ($('.property-list').length) {
        let loading = false;
        
        $(window).scroll(function() {
            if ($(window).scrollTop() + $(window).height() > $(document).height() - 100) {
                if (!loading) {
                    loading = true;
                    // loadMoreProperties();
                }
            }
        });
    }

    // Form validation
    $('.needs-validation').submit(function(event) {
        const form = this;
        if (form.checkValidity() === false) {
            event.preventDefault();
            event.stopPropagation();
        }
        $(form).addClass('was-validated');
    });

    // Contact form modal
    $('.contact-landlord-btn').click(function(e) {
        e.preventDefault();
        const propertyTitle = $(this).data('property-title');
        const landlordName = $(this).data('landlord-name');
        
        const modal = $(`
            <div class="modal fade" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Contact Landlord</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form>
                                <div class="mb-3">
                                    <label class="form-label">Property</label>
                                    <input type="text" class="form-control" value="${propertyTitle}" readonly>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Message</label>
                                    <textarea class="form-control" rows="4" placeholder="I'm interested in this property..."></textarea>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary">Send Message</button>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        $('body').append(modal);
        modal.modal('show');
        
        modal.on('hidden.bs.modal', function() {
            modal.remove();
        });
    });

});

// Utility functions
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function isAuthenticated() {
    return document.body.getAttribute('data-authenticated') === 'true';
}

function showToast(message, type = 'info') {
    const toast = $(`
        <div class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'primary'}" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `);
    
    $('.toast-container').append(toast);
    new bootstrap.Toast(toast[0]).show();
    
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Initialize map (if needed)
function initializeMap(containerId, lat, lng) {
    // This would integrate with a mapping service like Google Maps or Mapbox
    console.log(`Initialize map for ${containerId} at ${lat}, ${lng}`);
}

// Property comparison functionality (future feature)
const propertyComparison = {
    properties: [],
    
    add: function(propertyId) {
        if (this.properties.length < 3 && !this.properties.includes(propertyId)) {
            this.properties.push(propertyId);
            this.updateUI();
        }
    },
    
    remove: function(propertyId) {
        this.properties = this.properties.filter(id => id !== propertyId);
        this.updateUI();
    },
    
    updateUI: function() {
        $('.comparison-count').text(this.properties.length);
        $('.compare-btn').toggle(this.properties.length > 0);
    }
};

// Search filters
const searchFilters = {
    apply: function() {
        const form = $('.filter-form');
        const formData = new FormData(form[0]);
        const params = new URLSearchParams(formData);
        
        // Update URL without page reload
        const newUrl = `${window.location.pathname}?${params.toString()}`;
        window.history.pushState({}, '', newUrl);
        
        // Reload property listings
        this.loadProperties(params.toString());
    },
    
    loadProperties: function(queryString) {
        $.ajax({
            url: `/properties/?${queryString}`,
            success: function(data) {
                $('.property-listings').html($(data).find('.property-listings').html());
                $('.pagination').html($(data).find('.pagination').html());
            }
        });
    }
}; 