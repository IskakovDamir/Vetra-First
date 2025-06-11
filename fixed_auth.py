"""
🔐 FIXED AUTHENTICATION for Vetra AI
Resolves OAuth2 callback issues with improved error handling and debugging
"""

import os
import json
import logging
import threading
import time
import socket
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']
USERS_DIR = 'users'
REDIRECT_URI = 'http://localhost:8080/oauth2callback'

class FixedAuthManager:
    def __init__(self):
        if not os.path.exists(USERS_DIR):
            os.makedirs(USERS_DIR)
            logger.info(f"✅ Created users directory: {USERS_DIR}")
        
        self.active_sessions = {}
        self.server = None
        self.server_thread = None
        self.authorization_results = {}  # Store results for async checking
        
    def find_free_port(self, start_port=8080, max_attempts=10):
        """Find a free port starting from start_port"""
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        raise Exception("No free ports available")
    
    def start_callback_server(self):
        """Start OAuth callback server with improved error handling"""
        if self.server is not None:
            return True
            
        try:
            # Find a free port
            port = self.find_free_port()
            
            # Update redirect URI if port changed
            global REDIRECT_URI
            REDIRECT_URI = f'http://localhost:{port}/oauth2callback'
            
            # Create and start server
            self.server = HTTPServer(('localhost', port), FixedOAuthCallbackHandler)
            self.server.auth_manager = self
            self.server.timeout = 1  # Add timeout for proper shutdown
            
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            # Wait a moment to ensure server starts
            time.sleep(0.5)
            
            logger.info(f"✅ OAuth callback server started on localhost:{port}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Server start error: {e}")
            self.server = None
            return False
    
    def _run_server(self):
        """Run server with proper error handling"""
        try:
            logger.info("🔄 Starting OAuth callback server...")
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"❌ Server error: {e}")
        finally:
            logger.info("🔄 OAuth callback server stopped")
    
    def stop_callback_server(self):
        """Stop the callback server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            logger.info("✅ OAuth callback server stopped")
    
    def get_user_token_path(self, user_id):
        return os.path.join(USERS_DIR, f"user_{user_id}_token.json")
    
    def get_user_info_path(self, user_id):
        return os.path.join(USERS_DIR, f"user_{user_id}_info.json")
    
    def is_user_authorized(self, user_id):
        """Check if user is authorized with detailed logging"""
        token_path = self.get_user_token_path(user_id)
        
        logger.info(f"🔍 Checking authorization for user {user_id}")
        logger.info(f"📁 Token path: {token_path}")
        
        if not os.path.exists(token_path):
            logger.info(f"❌ No token file found for user {user_id}")
            return False
        
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
            if not creds:
                logger.warning(f"⚠️ Invalid credentials for user {user_id}")
                return False
            
            if creds.valid:
                logger.info(f"✅ Valid credentials for user {user_id}")
                return True
            
            if creds.expired and creds.refresh_token:
                try:
                    logger.info(f"🔄 Refreshing expired token for user {user_id}")
                    creds.refresh(Request())
                    self.save_user_credentials(user_id, creds)
                    logger.info(f"✅ Token refreshed for user {user_id}")
                    return True
                except Exception as e:
                    logger.error(f"❌ Token refresh failed for user {user_id}: {e}")
                    return False
            
            logger.warning(f"⚠️ Expired token without refresh token for user {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Auth check error for user {user_id}: {e}")
            return False
    
    def get_user_credentials(self, user_id):
        """Get user credentials with comprehensive error handling"""
        token_path = self.get_user_token_path(user_id)
        
        if not os.path.exists(token_path):
            logger.warning(f"⚠️ No token file for user {user_id}")
            return None
        
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
            if not creds:
                logger.warning(f"⚠️ Invalid credentials file for user {user_id}")
                return None
            
            if creds.expired and creds.refresh_token:
                try:
                    logger.info(f"🔄 Auto-refreshing token for user {user_id}")
                    creds.refresh(Request())
                    self.save_user_credentials(user_id, creds)
                    logger.info(f"✅ Token auto-refreshed for user {user_id}")
                except Exception as e:
                    logger.error(f"❌ Auto-refresh failed for user {user_id}: {e}")
                    return None
            
            return creds
            
        except Exception as e:
            logger.error(f"❌ Credentials retrieval error for user {user_id}: {e}")
            return None
    
    def save_user_credentials(self, user_id, credentials):
        """Save user credentials with backup"""
        token_path = self.get_user_token_path(user_id)
        backup_path = token_path + '.backup'
        
        try:
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            
            # Create backup if file exists
            if os.path.exists(token_path):
                try:
                    with open(token_path, 'r') as f:
                        backup_data = f.read()
                    with open(backup_path, 'w') as f:
                        f.write(backup_data)
                    logger.info(f"📋 Created backup for user {user_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Backup creation failed: {e}")
            
            # Save new credentials
            with open(token_path, 'w') as token_file:
                token_file.write(credentials.to_json())
            
            logger.info(f"✅ Token saved for user {user_id}")
            
            # Remove backup on success
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Token save error for user {user_id}: {e}")
            
            # Restore backup if available
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, 'r') as f:
                        backup_data = f.read()
                    with open(token_path, 'w') as f:
                        f.write(backup_data)
                    logger.info(f"✅ Restored backup for user {user_id}")
                    os.remove(backup_path)
                except Exception as restore_error:
                    logger.error(f"❌ Backup restore failed: {restore_error}")
            
            return False
    
    def save_user_info(self, user_id, user_data):
        """Save user info with detailed logging"""
        info_path = self.get_user_info_path(user_id)
        
        user_data['registered_at'] = datetime.now().isoformat()
        user_data['user_id'] = user_id
        user_data['last_updated'] = datetime.now().isoformat()
        
        try:
            os.makedirs(os.path.dirname(info_path), exist_ok=True)
            
            with open(info_path, 'w', encoding='utf-8') as info_file:
                json.dump(user_data, info_file, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ User info saved for {user_id}")
            logger.info(f"📊 Saved data: {json.dumps(user_data, indent=2, ensure_ascii=False)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Info save error for user {user_id}: {e}")
            return False
    
    def get_user_info(self, user_id):
        """Get user info with error handling"""
        info_path = self.get_user_info_path(user_id)
        
        if not os.path.exists(info_path):
            logger.info(f"ℹ️ No info file for user {user_id}")
            return None
        
        try:
            with open(info_path, 'r', encoding='utf-8') as info_file:
                data = json.load(info_file)
            logger.info(f"✅ User info loaded for {user_id}")
            return data
        except Exception as e:
            logger.error(f"❌ Info read error for user {user_id}: {e}")
            return None
    
    def get_google_user_profile(self, credentials):
        """Get Google user profile with comprehensive error handling"""
        try:
            logger.info("📊 Fetching Google user profile...")
            service = build('calendar', 'v3', credentials=credentials)
            
            # Test connection first
            try:
                calendar_list_result = service.calendarList().list(maxResults=10).execute()
                logger.info("✅ Google Calendar API connection successful")
            except HttpError as e:
                logger.error(f"❌ Google Calendar API error: {e}")
                return None
            
            calendar_list = calendar_list_result.get('items', [])
            
            primary_calendar = None
            calendar_count = len(calendar_list)
            
            for calendar in calendar_list:
                if calendar.get('primary', False):
                    primary_calendar = {
                        'id': calendar['id'],
                        'summary': calendar.get('summary', 'Primary Calendar'),
                        'timezone': calendar.get('timeZone', 'UTC'),
                        'access_role': calendar.get('accessRole', 'unknown')
                    }
                    logger.info(f"✅ Primary calendar found: {primary_calendar['summary']}")
                    break
            
            if not primary_calendar:
                logger.warning("⚠️ No primary calendar found")
            
            profile_data = {
                'primary_calendar': primary_calendar,
                'calendar_count': calendar_count,
                'calendars': calendar_list[:5],  # Store first 5 calendars
                'profile_fetched_at': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Profile data collected: {calendar_count} calendars")
            return profile_data
            
        except Exception as e:
            logger.error(f"❌ Profile fetch error: {e}")
            return None
    
    def create_authorization_url(self, user_id):
        """Create authorization URL with improved error handling"""
        try:
            logger.info(f"🔐 Creating authorization URL for user {user_id}")
            
            # Start callback server
            if not self.start_callback_server():
                logger.error("❌ Failed to start callback server")
                return None
            
            # Check credentials file
            if not os.path.exists('credentials.json'):
                logger.error("❌ credentials.json not found")
                return None
            
            logger.info(f"📁 Using redirect URI: {REDIRECT_URI}")
            
            # Create flow
            flow = Flow.from_client_secrets_file(
                'credentials.json',
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )
            
            # Generate authorization URL
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            # Store session
            self.active_sessions[state] = {
                'user_id': user_id,
                'flow': flow,
                'created_at': datetime.now(),
                'redirect_uri': REDIRECT_URI
            }
            
            logger.info(f"✅ Auth URL created for user {user_id}")
            logger.info(f"🔗 State: {state}")
            logger.info(f"🌐 Auth URL: {auth_url}")
            
            return auth_url
            
        except Exception as e:
            logger.error(f"❌ Auth URL creation error: {e}")
            return None
    
    def handle_oauth_callback(self, state, code, error=None):
        """Handle OAuth callback with comprehensive error handling"""
        try:
            logger.info(f"🔄 Processing OAuth callback")
            logger.info(f"📝 State: {state}")
            logger.info(f"📝 Code: {code[:20] if code else 'None'}...")
            logger.info(f"❌ Error: {error}")
            
            if error:
                logger.error(f"❌ OAuth error from Google: {error}")
                return None
            
            if state not in self.active_sessions:
                logger.error(f"❌ Unknown session state: {state}")
                logger.info(f"🔍 Active sessions: {list(self.active_sessions.keys())}")
                return None
            
            session = self.active_sessions[state]
            user_id = session['user_id']
            flow = session['flow']
            
            logger.info(f"✅ Session found for user {user_id}")
            
            # Exchange code for token
            logger.info("🔄 Exchanging code for token...")
            flow.fetch_token(code=code)
            creds = flow.credentials
            
            if not creds:
                logger.error("❌ Failed to get credentials from flow")
                return None
            
            logger.info("✅ Credentials obtained from Google")
            
            # Save credentials
            if not self.save_user_credentials(user_id, creds):
                logger.error(f"❌ Failed to save credentials for user {user_id}")
                return None
            
            logger.info(f"✅ Credentials saved for user {user_id}")
            
            # Get and save user profile
            logger.info("📊 Fetching user profile...")
            user_profile = self.get_google_user_profile(creds)
            if user_profile:
                self.save_user_info(user_id, user_profile)
                logger.info(f"✅ User profile saved for user {user_id}")
            else:
                logger.warning(f"⚠️ Could not fetch user profile for user {user_id}")
            
            # Store result for async checking
            self.authorization_results[user_id] = {
                'success': True,
                'timestamp': datetime.now(),
                'profile': user_profile
            }
            
            # Clean up session
            del self.active_sessions[state]
            
            logger.info(f"🎉 Authorization completed successfully for user {user_id}")
            return user_id
            
        except Exception as e:
            logger.error(f"❌ Callback handling error: {e}")
            logger.exception("Full exception details:")
            return None
    
    def check_authorization_result(self, user_id):
        """Check if authorization was completed"""
        if user_id in self.authorization_results:
            result = self.authorization_results[user_id]
            del self.authorization_results[user_id]  # Remove after checking
            return result
        return None
    
    def revoke_user_authorization(self, user_id):
        """Revoke user authorization with detailed logging"""
        logger.info(f"🔄 Revoking authorization for user {user_id}")
        
        token_path = self.get_user_token_path(user_id)
        info_path = self.get_user_info_path(user_id)
        
        files_removed = 0
        for file_path, file_type in [(token_path, 'token'), (info_path, 'info')]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    files_removed += 1
                    logger.info(f"✅ Removed {file_type} file for user {user_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to remove {file_type} file: {e}")
        
        # Clean up any pending results
        if user_id in self.authorization_results:
            del self.authorization_results[user_id]
        
        logger.info(f"✅ Authorization revoked for user {user_id} ({files_removed} files removed)")
        return files_removed > 0


class FixedOAuthCallbackHandler(BaseHTTPRequestHandler):
    """Fixed OAuth callback handler with better error handling and debugging"""
    
    def do_GET(self):
        """Handle GET request from Google OAuth with comprehensive logging"""
        try:
            logger.info(f"📥 Received callback request: {self.path}")
            
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            logger.info(f"📊 Parsed URL: {parsed_url}")
            logger.info(f"📊 Query params: {query_params}")
            
            if parsed_url.path == '/oauth2callback':
                state = query_params.get('state', [None])[0]
                code = query_params.get('code', [None])[0]
                error = query_params.get('error', [None])[0]
                
                logger.info(f"📝 Extracted - State: {state}, Code: {'Present' if code else 'None'}, Error: {error}")
                
                if error:
                    error_description = query_params.get('error_description', ['Unknown error'])[0]
                    logger.error(f"❌ OAuth error: {error} - {error_description}")
                    self.send_error_response(f"Authorization error: {error}")
                    return
                
                if not state or not code:
                    logger.error("❌ Missing required parameters")
                    self.send_error_response("Missing required parameters (state or code)")
                    return
                
                # Process callback
                user_id = self.server.auth_manager.handle_oauth_callback(state, code, error)
                
                if user_id:
                    logger.info(f"✅ Callback processed successfully for user {user_id}")
                    self.send_success_response(user_id)
                else:
                    logger.error("❌ Callback processing failed")
                    self.send_error_response("Authorization completion error")
            else:
                logger.warning(f"⚠️ Unknown path: {parsed_url.path}")
                self.send_404()
                
        except Exception as e:
            logger.error(f"❌ Callback handling exception: {e}")
            logger.exception("Full exception details:")
            self.send_error_response(f"Internal error: {str(e)}")
    
    def send_success_response(self, user_id):
        """Send enhanced success response"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>✅ Authorization Complete</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    text-align: center; 
                    margin: 0;
                    padding: 40px 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .container {{ 
                    background: white; 
                    padding: 40px; 
                    border-radius: 15px; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2); 
                    max-width: 500px;
                    width: 100%;
                }}
                .success {{ 
                    color: #28a745; 
                    font-size: 32px; 
                    margin-bottom: 20px; 
                    font-weight: bold;
                }}
                .message {{ 
                    color: #333; 
                    font-size: 18px; 
                    line-height: 1.6;
                    margin-bottom: 30px;
                }}
                .details {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    font-size: 14px;
                    color: #666;
                }}
                .countdown {{
                    font-size: 16px;
                    color: #666;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅ Authorization Successful!</div>
                <div class="message">
                    Great! Your Google Calendar has been connected to Vetra AI.
                </div>
                <div class="details">
                    <strong>User ID:</strong> {user_id}<br>
                    <strong>Status:</strong> Ready to create events<br>
                    <strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </div>
                <div class="message">
                    You can now return to the Telegram bot and start creating events with natural language!
                </div>
                <div class="countdown" id="countdown">
                    This page will close automatically in <span id="timer">5</span> seconds.
                </div>
            </div>
            <script>
                let seconds = 5;
                const timer = document.getElementById('timer');
                const countdown = setInterval(() => {{
                    seconds--;
                    timer.textContent = seconds;
                    if (seconds <= 0) {{
                        clearInterval(countdown);
                        window.close();
                    }}
                }}, 1000);
            </script>
        </body>
        </html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
        
        logger.info(f"✅ Success response sent for user {user_id}")
    
    def send_error_response(self, error_message):
        """Send enhanced error response"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>❌ Authorization Error</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    text-align: center; 
                    margin: 0;
                    padding: 40px 20px;
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .container {{ 
                    background: white; 
                    padding: 40px; 
                    border-radius: 15px; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2); 
                    max-width: 500px;
                    width: 100%;
                }}
                .error {{ 
                    color: #dc3545; 
                    font-size: 32px; 
                    margin-bottom: 20px; 
                    font-weight: bold;
                }}
                .message {{ 
                    color: #333; 
                    font-size: 18px; 
                    line-height: 1.6;
                    margin-bottom: 30px;
                }}
                .error-details {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    font-size: 14px;
                    color: #666;
                    text-align: left;
                }}
                .suggestions {{
                    background: #e3f2fd;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    text-align: left;
                }}
                .suggestions h4 {{
                    margin-top: 0;
                    color: #1976d2;
                }}
                .suggestions ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error">❌ Authorization Error</div>
                <div class="message">
                    Unfortunately, there was an error during the authorization process.
                </div>
                <div class="error-details">
                    <strong>Error:</strong> {error_message}<br>
                    <strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </div>
                <div class="suggestions">
                    <h4>🔧 What to try:</h4>
                    <ul>
                        <li>Go back to Telegram and try /auth again</li>
                        <li>Make sure you allow all requested permissions</li>
                        <li>Check if your browser blocks popups</li>
                        <li>Try using a different browser</li>
                        <li>Contact the developer if the issue persists</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        
        self.send_response(400)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
        
        logger.error(f"❌ Error response sent: {error_message}")
    
    def send_404(self):
        """Send enhanced 404 response"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>404 Not Found</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 100px; }
                .container { max-width: 500px; margin: 0 auto; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>404 Not Found</h1>
                <p>The requested page was not found.</p>
                <p>This is the Vetra AI OAuth callback server.</p>
            </div>
        </body>
        </html>
        """
        
        self.send_response(404)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
        
        logger.warning(f"⚠️ 404 response sent for path: {self.path}")
    
    def log_message(self, format, *args):
        """Custom logging for HTTP requests"""
        logger.info(f"🌐 HTTP: {format % args}")


# Global instance
fixed_auth_manager = FixedAuthManager()

def get_user_calendar_service(user_id):
    """Get Google Calendar service for specific user with improved error handling"""
    try:
        logger.info(f"🔄 Creating calendar service for user {user_id}")
        
        creds = fixed_auth_manager.get_user_credentials(user_id)
        if not creds:
            logger.warning(f"⚠️ No credentials for user {user_id}")
            return None
        
        if not creds.valid:
            logger.warning(f"⚠️ Invalid credentials for user {user_id}")
            return None
        
        service = build('calendar', 'v3', credentials=creds)
        
        # Test connection with a simple API call
        try:
            test_result = service.calendarList().list(maxResults=1).execute()
            logger.info(f"✅ Calendar service created and tested for user {user_id}")
            return service
        except HttpError as e:
            logger.error(f"❌ Calendar service test failed for user {user_id}: {e}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Service creation error for user {user_id}: {e}")
        return None

# Test function for debugging
def test_oauth_flow():
    """Test the OAuth flow for debugging"""
    print("🧪 Testing OAuth Flow Components...")
    
    # Test 1: Check credentials file
    if os.path.exists('credentials.json'):
        print("✅ credentials.json found")
        try:
            with open('credentials.json', 'r') as f:
                creds_data = json.load(f)
            print(f"✅ credentials.json is valid JSON")
            
            web_config = creds_data.get('web', {})
            client_id = web_config.get('client_id', 'NOT_FOUND')
            redirect_uris = web_config.get('redirect_uris', [])
            
            print(f"📝 Client ID: {client_id[:20]}...")
            print(f"📝 Redirect URIs: {redirect_uris}")
            
        except Exception as e:
            print(f"❌ credentials.json error: {e}")
    else:
        print("❌ credentials.json not found")
    
    # Test 2: Check port availability
    try:
        port = fixed_auth_manager.find_free_port()
        print(f"✅ Free port found: {port}")
    except Exception as e:
        print(f"❌ Port finding error: {e}")
    
    # Test 3: Test server startup
    try:
        if fixed_auth_manager.start_callback_server():
            print("✅ Callback server started successfully")
            fixed_auth_manager.stop_callback_server()
            print("✅ Callback server stopped successfully")
        else:
            print("❌ Callback server failed to start")
    except Exception as e:
        print(f"❌ Server test error: {e}")
    
    # Test 4: Test OAuth flow creation
    try:
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri='http://localhost:8080/oauth2callback'
        )
        print("✅ OAuth flow creation successful")
    except Exception as e:
        print(f"❌ OAuth flow creation error: {e}")
    
    print("🧪 OAuth flow test completed")

if __name__ == "__main__":
    # Run tests when script is executed directly
    test_oauth_flow()