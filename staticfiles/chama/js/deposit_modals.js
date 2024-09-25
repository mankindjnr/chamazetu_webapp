document.getElementById('directDepositForm').addEventListener('submit', function(event) {
    const form = event.target;
    let isValid = true;

    // Clear previous error messages
    document.querySelectorAll('.error-message').forEach(el => el.textContent = '');

    // Validate amount
    const amount = form.amount;
    if (amount.value.trim() === '' || amount.value <= 0) {
      isValid = false;
      amount.nextElementSibling.textContent = 'Please enter a valid amount.';
    }

    // Validate phone number
    const phoneNumber = form.phonenumber;
    const phoneNumberPattern = /^\d{9}$/;
    if (!phoneNumberPattern.test(phoneNumber.value)) {
      isValid = false;
      phoneNumber.nextElementSibling.textContent = 'Phone number should be exactly 9 digits.';
    }

    if (!isValid) {
      event.preventDefault();
    }
  });