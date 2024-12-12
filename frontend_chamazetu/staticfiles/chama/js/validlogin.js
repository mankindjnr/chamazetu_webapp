document.addEventListener("DOMContentLoaded", function () {
    const signupform = document.getElementById('signup');
    const username = document.getElementById('username');
    const email = document.getElementById('email');
    const password = document.getElementById('password');
    const password2 = document.getElementById('password2');

    signupform.addEventListener('submit', (e) => {
        e.preventDefault();

        checkInputs();
    });

    function checkInputs() {
        // get the values from the inputs

        const usernameValue = username.value.trim();
        const emailValue = email.value.trim();
        const passwordValue = password.value.trim();
        const password2Value = password2.value.trim();

        if (usernameValue === '') {
            setErrorFor(username, 'username cannot be blank');
        } else {
            setSuccessFor(username);
        }

        if (emailValue === '') {
            setErrorFor(email, 'Email cannot be blank');
        } else {
            setSuccessFor(email);
        }

        if (passwordValue === '') {
            setErrorFor(password, 'password cannot be blank');
        } else {
            setSuccessFor(password);
        }

        if (password2Value === '') {
            setErrorFor(password2, 'paswsord cannot be blank');
        } else if (password2Value !== passwordValue) {
            setErrorFor(password2, 'passwords do not match');
        } else {
            setSuccessFor(password2);
        }

        if (password2Value === '' || password2Value !== passwordValue) {
            setErrorFor(password2, 'passwords do not match');
        } else {
            setSuccessFor(password2);
        }
    }


    function setErrorFor(input, message) {
        const formControl = input.parentElement; // .form-control
        const small = formControl.querySelector('small');
        formControl.classList.add('error');
        // add error message inside small tag in the form-control class
        small.innerText = message;

        // add error class
        //formControl.className = 'form-floating error';
    }

    function setSuccessFor(input) {
        const formControl = input.parentElement;
        formControl.classList.remove("error")
        formControl.classList.add('success');
    }
});