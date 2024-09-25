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
    // const lastJoiningDate = new Date(form.last_joining_date.value);
    // const firstContributionDate = new Date(form.first_contribution_date.value);

    // Get the date input values
    const lastJoiningDateValue = document.getElementById('last_joining_date').value;
    const firstContributionDateValue = document.getElementById('first_contribution_date').value;

    // Create Date objects
    const lastJoiningDate = new Date(lastJoiningDateValue);
    const firstContributionDate = new Date(firstContributionDateValue);
    if (firstContributionDate <= lastJoiningDate) {
      isValid = false;
      document.getElementById('dateHelp').textContent = 'First contribution date should be past the final day of joining';
    }

    // Validate first contribution date matches contribution frequency
    
    const frequency = form.frequency.value;
    if (frequency === 'weekly') {
      const weeklyDay = form.weekly_day.value;
      const daysOfWeek = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
      if (firstContributionDate.getDay() !== daysOfWeek.indexOf(weeklyDay)) {
        isValid = false;
        form.first_contribution_date.nextElementSibling.textContent = 'First contribution date should match the selected day of the week';
      }
    } else if (frequency === 'monthly') {
      const monthlyDay = parseInt(form.monthly_day.value, 10);
      if (firstContributionDate.getDate() !== monthlyDay) {
        isValid = false;
        form.first_contribution_date.nextElementSibling.textContent = 'First contribution date should match the entered day of the month';
      }
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