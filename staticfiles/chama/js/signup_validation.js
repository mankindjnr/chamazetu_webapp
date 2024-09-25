document.getElementById('signupForm').addEventListener('submit', function (event) {
    const form = event.target;
    const firstName = form.first_name;
    const lastName = form.last_name;
    const email = form.email;
    const password = form.password;
    const password2 = form.password2;
    
    let isValid = true;

    // Clear previous error messages
    document.querySelectorAll('.error-message').forEach(el => el.textContent = '');

    // Validate First Name
    if (!firstName.value.trim()) {
      isValid = false;
      firstName.nextElementSibling.textContent = 'First name is required';
    }

    // Validate Last Name
    if (!lastName.value.trim()) {
      isValid = false;
      lastName.nextElementSibling.textContent = 'Last name is required';
    }

    // Validate Email
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.value.trim() || !emailPattern.test(email.value)) {
      isValid = false;
      email.nextElementSibling.nextElementSibling.textContent = 'Please enter a valid Email address';
    }

    // Validate Password
    if (!password.value.trim()) {
      isValid = false;
      password.nextElementSibling.nextElementSibling.textContent = 'Password is required';
    }

    // Validate Confirm Password
    if (password.value !== password2.value) {
      isValid = false;
      password2.nextElementSibling.nextElementSibling.textContent = 'Passwords do not match';
    }

    if (!isValid) {
      event.preventDefault();
    }
  });