from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from django.contrib.messages import get_messages

from .models import Profile
from .otp_utils import generate_otp_code, setup_user_otp, verify_otp_code, send_otp_email

class OTPVerificationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Create standard test user
        self.username = "testuser@example.com"
        self.password = "securepassword123"
        self.user = User.objects.create_user(
            username=self.username,
            email=self.username,
            password=self.password,
            first_name="Test",
            last_name="User"
        )
        self.profile, _ = Profile.objects.get_or_create(user=self.user)

    def test_otp_generation(self):
        """Test that the OTP code is a secure 6-digit number."""
        code = generate_otp_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_otp_setup(self):
        """Test that setting up user OTP hashes and saves values correctly."""
        raw_otp = setup_user_otp(self.profile)
        self.assertEqual(len(raw_otp), 6)
        
        # Verify it's hashed in the DB and has a 10-minute expiry
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.otp_code, raw_otp)
        self.assertTrue(self.profile.otp_code.startswith("pbkdf2_"))
        self.assertIsNotNone(self.profile.otp_expiry)
        
        # Check that it expires in ~10 mins
        now = timezone.now()
        self.assertTrue(now < self.profile.otp_expiry <= now + timedelta(minutes=10))
        self.assertEqual(self.profile.otp_attempts, 0)

    def test_otp_verification_success(self):
        """Test that verification succeeds with a correct code."""
        raw_otp = setup_user_otp(self.profile)
        
        success, message = verify_otp_code(self.profile, raw_otp)
        self.assertTrue(success)
        self.assertEqual(message, "Email verified successfully!")
        
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_email_verified)
        self.assertIsNone(self.profile.otp_code)
        self.assertIsNone(self.profile.otp_expiry)
        self.assertEqual(self.profile.otp_attempts, 0)

    def test_otp_verification_failure_and_lockout(self):
        """Test that incorrect codes fail, increment attempts, and trigger a brute force lockout at 5 failures."""
        raw_otp = setup_user_otp(self.profile)
        incorrect_otp = "111111" if raw_otp != "111111" else "222222"
        
        # 1st attempt
        success, message = verify_otp_code(self.profile, incorrect_otp)
        self.assertFalse(success)
        self.assertIn("attempts remaining", message)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.otp_attempts, 1)
        
        # Make 3 more incorrect attempts (total 4)
        for i in range(3):
            verify_otp_code(self.profile, incorrect_otp)
            
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.otp_attempts, 4)
        
        # 5th attempt - should trigger lockout
        success, message = verify_otp_code(self.profile, incorrect_otp)
        self.assertFalse(success)
        self.assertIn("Too many failed attempts", message)
        
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.otp_code) # Code should be invalidated

    def test_otp_expiration(self):
        """Test that verification fails if the OTP has expired."""
        raw_otp = setup_user_otp(self.profile)
        
        # Simulate expiration (move expiry to 1 second ago)
        self.profile.otp_expiry = timezone.now() - timedelta(seconds=1)
        self.profile.save()
        
        success, message = verify_otp_code(self.profile, raw_otp)
        self.assertFalse(success)
        self.assertEqual(message, "This verification code has expired. Please request a new one.")

    def test_signup_redirects_and_restricts_login(self):
        """Test that signing up redirects to verification and sets session."""
        signup_url = reverse('signup')
        data = {
            'full_name': 'New User',
            'email': 'newuser@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        response = self.client.post(signup_url, data)
        self.assertRedirects(response, reverse('verify_otp'))
        
        # Check session email matches
        self.assertEqual(self.client.session.get('pre_verified_user_email'), 'newuser@example.com')
        
        # Verify the user is created but is unverified
        new_user = User.objects.get(email='newuser@example.com')
        self.assertFalse(new_user.profile.is_email_verified)
        self.assertIsNotNone(new_user.profile.otp_code)

    def test_login_denied_for_unverified_user(self):
        """Test that an unverified user cannot log in and gets redirected to OTP verification."""
        login_url = reverse('login')
        data = {
            'email': self.username,
            'password': self.password
        }
        
        # Unverified user login attempt
        response = self.client.post(login_url, data)
        self.assertRedirects(response, reverse('verify_otp'))
        self.assertEqual(self.client.session.get('pre_verified_user_email'), self.username)
        
        # Verify a new OTP code was generated and sent
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.otp_code)
        self.assertEqual(self.profile.otp_attempts, 0)

    def test_verify_otp_view_flows(self):
        """Test the OTP verification view submission flow."""
        # Setup session variables
        session = self.client.session
        session['pre_verified_user_email'] = self.username
        session.save()
        
        raw_otp = setup_user_otp(self.profile)
        
        # Submit correct OTP split across inputs
        data = {
            'otp_1': raw_otp[0],
            'otp_2': raw_otp[1],
            'otp_3': raw_otp[2],
            'otp_4': raw_otp[3],
            'otp_5': raw_otp[4],
            'otp_6': raw_otp[5],
        }
        verify_url = reverse('verify_otp')
        response = self.client.post(verify_url, data)
        
        # Verify redirect to dashboard
        self.assertRedirects(response, reverse('home'))
        
        # Check profile is verified
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_email_verified)
        
        # Check user is logged in
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_resend_cooldown_timer(self):
        """Test that the resend endpoint restricts spamming with a 60-second cooldown."""
        session = self.client.session
        session['pre_verified_user_email'] = self.username
        session.save()
        
        resend_url = reverse('resend_otp')
        
        # First request succeeds
        response1 = self.client.post(resend_url)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.json().get('success'))
        
        # Immediate second request fails with 429
        response2 = self.client.post(resend_url)
        self.assertEqual(response2.status_code, 429)
        self.assertFalse(response2.json().get('success'))
        self.assertIn("wait", response2.json().get('message'))
