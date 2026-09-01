window.TESTFOODO_CONFIG = {
  API_BASE_URL:
    window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
      ? "http://127.0.0.1:8000/api/v1"
      : "https://testfoodo-api.onrender.com/api/v1",
};

