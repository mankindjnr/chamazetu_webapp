document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('signup');
    form.addEventListener('submit', function (event) {
        let isValid = true;

        // Check if the first name field is empty
        const firstNameField = document.getElementById('firstname');
        if (firstNameField.value.trim() === '') {
            isValid = false;
            displayError(firstNameField, 'First name is required.');
        } else if (containsNonAlphaNumeric(firstNameField.value.trim())) {
            isValid = false;
            displayError(firstNameField, 'First name must only contain alphanumeric characters.');
        } else {
            clearError(firstNameField);
        }

        // Check if the last name field is empty
        const lastNameField = document.getElementById('lastname');
        if (lastNameField.value.trim() === '') {
            isValid = false;
            displayError(lastNameField, 'Last name is required.');
        } else if (containsNonAlphaNumeric(lastNameField.value.trim())) {
            isValid = false;
            displayError(lastNameField, 'Last name must only contain alphanumeric characters.');
        } else {
            clearError(lastNameField);
        }

        // Check if the email field is empty and validate its format
        const emailField = document.getElementById('email');
        const emailValue = emailField.value.trim();
        if (emailValue === '') {
            isValid = false;
            displayError(emailField, 'An email is required.');
        } else if (!isValidEmail(emailValue)) {
            isValid = false;
            displayError(emailField, 'Email is not valid.');
        } else {
            clearError(emailField);
        }

        // Check if the password field is empty
        const passwordField = document.getElementById('password');
        if (passwordField.value.trim() === '') {
            isValid = false;
            displayError(passwordField, 'Password is required.');
        } else if (passwordField.value.trim().length < 8) {
            isValid = false;
            displayError(passwordField, 'Password must be at least 8 characters long.');
        } else {
            clearError(passwordField);
        }

        // Check if the password confirmation field is empty
        const password2Field = document.getElementById('password2');
        if (password2Field.value.trim() === '') {
            isValid = false;
            displayError(password2Field, 'Confirmation password is required.');
        } else if (password2Field.value.trim() !== passwordField.value.trim()) {
            isValid = false;
            displayError(password2Field, 'Passwords do not match.');
        } else {
            clearError(password2Field);
        }

        // Prevent form submission if any validation error
        if (!isValid) {
            event.preventDefault();
        }
    });

    function displayError(field, message) {
        const errorDiv = field.nextElementSibling;
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    function clearError(field) {
        const errorDiv = field.nextElementSibling;
        errorDiv.textContent = '';
        errorDiv.style.display = 'none';
    }

    function isValidEmail(email) {
        // Regular expression for basic email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    function containsNonAlphaNumeric(str) {
        const regex = /[^a-zA-Z0-9]/;
        return regex.test(str);
    }
/*
    function isSafeInput(input) {
        // Check for single quotes, double quotes, SQL keywords, and operators
        const sqlKeywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "UNION", "OR", "AND"];
        const sqlOperators = ["=", "<", ">"];
        const sqlPattern = new RegExp(`(${sqlKeywords.join("|")}|${sqlOperators.join("|")}|['"])`, "i");
      
        // Check for HTML tags and JavaScript event handlers
        const htmlPattern = /<\s*(script|img|a)|on\w+\s*=/i;
      
        // Check for path traversal attempts
        const pathTraversalPattern = /\.\.\//;
      
        // Check for special characters that can manipulate HTML
        const specialCharactersPattern = /[<>&]/;
      
        // Check for CSRF tokens (assuming they start with 'csrf_token=')
        const csrfPattern = /^csrf_token=/i;
      
        // Check for any of the patterns
        if (
          sqlPattern.test(input) ||
          htmlPattern.test(input) ||
          pathTraversalPattern.test(input) ||
          specialCharactersPattern.test(input) ||
          csrfPattern.test(input)
        )
        if (isSafeInput(userInput)) {
        // Input is safe, process it
         {
          return false; // Input contains potentially malicious content
        }
      
        return true; // Input is safe
      }
      */
});
