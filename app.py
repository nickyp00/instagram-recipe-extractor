from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import time
import sys

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
        print("ERROR: APIFY_TOKEN not set", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': 'Server configuration error: APIFY_TOKEN not set'
        }), 500
    
    # Get URL from request
    data = request.get_json()
    
    if not data or 'url' not in data:
        print("ERROR: Missing url parameter", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': 'Missing "url" parameter in request body'
        }), 400
    
    instagram_url = data['url']
    
    if not instagram_url or not isinstance(instagram_url, str):
        print(f"ERROR: Invalid URL format: {instagram_url}", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': 'Invalid URL format'
        }), 400
    
    # Validate it's an Instagram URL
    if 'instagram.com' not in instagram_url:
        print(f"ERROR: Not an Instagram URL: {instagram_url}", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': 'URL must be from instagram.com'
        }), 400
    
    try:
        # Log the extraction attempt
        print(f"===== EXTRACTION STARTED =====", file=sys.stderr)
        print(f"Instagram URL: {instagram_url}", file=sys.stderr)
        print(f"Token configured: {bool(APIFY_TOKEN)}", file=sys.stderr)
        print(f"Token first 20 chars: {APIFY_TOKEN[:20]}...", file=sys.stderr)
        
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
        
        print(f"Calling Apify API...", file=sys.stderr)
        print(f"Payload: {payload}", file=sys.stderr)
        
        # Make request to Apify (with timeout)
        response = requests.post(apify_url, json=payload, headers=headers, timeout=60)
        
        print(f"Apify response status: {response.status_code}", file=sys.stderr)
        print(f"Apify response body (first 500 chars): {response.text[:500]}", file=sys.stderr)
        
        # Check if request was successful
        if response.status_code != 200:
            error_message = 'Failed to extract caption from Instagram'
            try:
                error_data = response.json()
                print(f"Apify error data: {error_data}", file=sys.stderr)
                if 'error' in error_data:
                    error_message = error_data['error'].get('message', error_message)
            except Exception as e:
                print(f"Could not parse error response: {e}", file=sys.stderr)
            
            print(f"ERROR: {error_message}", file=sys.stderr)
            return jsonify({
                'success': False,
                'error': error_message
            }), response.status_code
        
        # Parse response
        results = response.json()
        print(f"Apify returned {len(results)} results", file=sys.stderr)
        
        # Check if we got results
        if not results or len(results) == 0:
            print("ERROR: No results returned from Apify", file=sys.stderr)
            return jsonify({
                'success': False,
                'error': 'No data found. The post might be private, deleted, or the URL is invalid.'
            }), 404
        
        # Extract the first result
        post_data = results[0]
        print(f"Successfully extracted data for post: {post_data.get('shortCode', 'unknown')}", file=sys.stderr)
        print(f"Caption length: {len(post_data.get('caption', ''))}", file=sys.stderr)
        print(f"===== EXTRACTION COMPLETED =====", file=sys.stderr)
        
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
        print("ERROR: Request timed out", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': 'Request timed out. Please try again.'
        }), 504
    
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error: {str(e)}", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': f'Network error: {str(e)}'
        }), 503
    
    except Exception as e:
        print(f"ERROR: Unexpected error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
