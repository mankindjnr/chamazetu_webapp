// Function to get a cookie value by name
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

//function to parse the jwt token
// function parseJwt(token) {
//     try {
//         const base64Url = token.split('.')[1];
//         const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
//         const jsonPayload = decodeURIComponent(
//             atob(base64)
//                 .split('')
//                 .map(function (c) {
//                     return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
//                 })
//                 .join('')
//         );
//         return JSON.parse(jsonPayload);
//     } catch (e) {
//         console.error('Error parsing JWT:', e);
//         return null;
//     }
// }


// Function to check if the refresh token is valid
async function checkTokenValidity(refreshToken) {
    try {
        const response = await fetch('http://192.168.100.7:9400/auth/isTokenValid', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: refreshToken })
        });

        if (!response.ok) {
            throw new Error('Token validation failed');
        }

        return await response.json();
    } catch (error) {
        console.error('Error checking token validity:', error);
        return { valid: false };
    }
}

// Function to refresh the access token
async function refreshAccessToken(username, role) {
    try {
        const response = await fetch('http://192.168.100.7:9400/auth/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username: username, role: role})
        });

        if (!response.ok) {
            throw new Error('Access token refresh failed');
        }

        return await response.json();
    } catch (error) {
        console.error('Error refreshing access token:', error);
        throw error;
    }
}

// Function to handle the token refresh process
async function handleTokenRefresh() {
    const refreshToken = getCookie('member_refresh_token');
    const username = getCookie('current_member')
    const role = 'member'

    if (!refreshToken) {
        console.error('Refresh token not found.');
        logoutUser();
        return;
    }

    const tokenValidityResponse = await checkTokenValidity(refreshToken);
    if (tokenValidityResponse.valid) {
        try {
            const refreshResponse = await refreshAccessToken(username, role);

            if (refreshResponse.new_access_token) {
                // Update the 'member_access_token' cookie with the new access token
                const newAccessToken = refreshResponse.new_access_token;
                console.log('New access token:', newAccessToken);
                document.cookie = `member_access_token=${newAccessToken}; path=/; Secure; SameSite=Strict`;
            } else {
                console.error('New access token not received.');
            }
        } catch (error) {
            console.error('Error refreshing access token:', error);
        }
    } else {
        console.error('Refresh token is not valid.');
        logoutUser();
    }
}

// Function to log out the user
function logoutUser() {
    console.log('Logging out user.');
    // Remove cookies
    document.cookie = 'member_access_token=; Max-Age=0; path=/; Secure; SameSite=Strict';
    document.cookie = 'member_refresh_token=; Max-Age=0; path=/; Secure; SameSite=Strict';
    // Redirect to the login page or perform other logout actions
    window.location.href = 'https://chamazetu.com/signin/member';
}

// Run the token refresh process every 10 minutes
setInterval(handleTokenRefresh, 4 * 60 * 1000);