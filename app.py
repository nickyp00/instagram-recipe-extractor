from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import time

app = Flask(__name__, static_folder='static')
CORS(app)

# Get API token from environment variable
APIFY_TOKEN = os.environ.get('APIFY_TOKEN', '')

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Instagram Recipe Extractor is running',
        'token_configured': bool(APIFY_TOKEN)
    })

@app.route('/extract', methods=['POST'])
def extract_caption():
    """
    Extract caption from Instagram reel
    
    Expected JSON body:
    {
        "url": "https://www.instagram.com/reel/ABC123/"
    }
    """
    
    # Validate API token is configured
    if not APIFY_TOKEN:
        return jsonify({
            'success': False,
            'error': 'Server configuration error: APIFY_TOKEN not set'
        }), 500
    
    # Get URL from request
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing "url" parameter in request body'
        }), 400
    
    instagram_url = data['url']
    
    if not instagram_url or not isinstance(instagram_url, str):
        return jsonify({
            'success': False,
            'error': 'Invalid URL format'
        }), 400
    
    # Validate it's an Instagram URL
    if 'instagram.com' not in instagram_url:
        return jsonify({
            'success': False,
            'error': 'URL must be from instagram.com'
        }), 400
    
    try:
        # Call Apify API (synchronous endpoint for immediate results)
        apify_url = f'https://api.apify.com/v2/acts/apify~instagram-reel-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}'
        
        payload = {
            "username": [instagram_url],
            "resultsLimit": 1,
            "includeSharesCount": False
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Make request to Apify (with timeout)
        response = requests.post(apify_url, json=payload, headers=headers, timeout=60)
        
        # Check if request was successful
        if response.status_code != 200:
            error_message = 'Failed to extract caption from Instagram'
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_message = error_data['error'].get('message', error_message)
            except:
                pass
            
            return jsonify({
                'success': False,
                'error': error_message
            }), response.status_code
        
        # Parse response
        results = response.json()
        
        # Check if we got results
        if not results or len(results) == 0:
            return jsonify({
                'success': False,
                'error': 'No data found. The post might be private, deleted, or the URL is invalid.'
            }), 404
        
        # Extract the first result
        post_data = results[0]
        
        # Return cleaned data
        return jsonify({
            'success': True,
            'data': {
                'caption': post_data.get('caption', ''),
                'url': post_data.get('url', instagram_url),
                'username': post_data.get('ownerUsername', 'Unknown'),
                'timestamp': post_data.get('timestamp', ''),
                'likes': post_data.get('likesCount', 0),
                'comments': post_data.get('commentsCount', 0),
                'views': post_data.get('videoViewCount', 0),
                'hashtags': post_data.get('hashtags', []),
                'mentions': post_data.get('mentions', []),
                'location': post_data.get('locationName', None)
            }
        }), 200
        
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Request timed out. Please try again.'
        }), 504
    
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Network error: {str(e)}'
        }), 503
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)