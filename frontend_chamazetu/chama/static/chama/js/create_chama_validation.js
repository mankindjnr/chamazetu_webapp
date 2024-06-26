document.getElementById('createChamaForm').addEventListener('submit', function (event) {
    const form = event.target;
    let isValid = true;

    // Clear previous error messages
    document.querySelectorAll('.error-message').forEach(el => el.textContent = '');

    // Validate alphanumeric fields
    const alphanumericPattern = /^[a-zA-Z0-9 ]+$/;
    ['chama_name', 'chama_type'].forEach(field => {
      const input = form[field];
      if (!input.value.trim() || !alphanumericPattern.test(input.value)) {
        isValid = false;
        input.nextElementSibling.textContent = `${input.previousElementSibling.textContent} should be alphanumeric and not empty`;
      }
    });

    // Validate description length
    const description = form.description;
    if (description.value.length > 500) {
      isValid = false;
      description.nextElementSibling.nextElementSibling.textContent = 'Description should not exceed 500 characters';
    }

    // Validate number of members
    const membersAllowed = form.members_allowed;
    if (!membersAllowed.value.trim() && !form.noLimit.checked) {
      isValid = false;
      membersAllowed.nextElementSibling.nextElementSibling.textContent = 'Please specify the number of members or check "No limit"';
    }

    // Validate that the first contribution date is after the last joining date
    const lastJoiningDate = new Date(form.last_joining_date.value);
    const firstContributionDate = new Date(form.first_contribution_date.value);
    if (firstContributionDate <= lastJoiningDate) {
      isValid = false;
      document.getElementById('dateHelp').textContent = 'First contribution date should be past the final day of joining';
    }

    if (!isValid) {
      event.preventDefault();
    }
  });

  function showOptions() {
    const frequency = document.getElementById('frequency').value;
    document.getElementById('weekly_options').style.display = frequency === 'weekly' ? 'block' : 'none';
    document.getElementById('monthly_options').style.display = frequency === 'monthly' ? 'block' : 'none';
  }