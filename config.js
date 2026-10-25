// Terravia chatbot API endpoint.
//
// GitHub Pages serves only static files, so the chatbot API must run elsewhere.
// Point this at wherever the API is reachable:
//   - Local demo:      run `uvicorn api:app --port 8000` and use localhost below.
//   - Hosted API:      set the full https URL of your deployed API.
//
// Leave empty ("") only when the API serves this site from the SAME origin
// (i.e. you ran it with TERRAVIA_SERVE_SITE=1).
const isLocalDemo = ['localhost', '127.0.0.1'].includes(window.location.hostname);
window.TERRAVIA_API = isLocalDemo ? '' : "https://terravia-api.onrender.com";
