import { BrowserRouter } from "react-router-dom";

import "./App.css";
import { AuthProvider } from "./auth/AuthContext";
import { AppRouter } from "./router";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
