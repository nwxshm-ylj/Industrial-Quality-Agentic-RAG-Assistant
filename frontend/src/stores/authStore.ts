import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { LoginResponse, Role, UserInfo } from "../api/types";

interface AuthState {
  accessToken: string | null;
  tokenType: string;
  user: UserInfo | null;
  isAuthenticated: boolean;
  setSession: (response: LoginResponse) => void;
  logout: () => void;
  hasRole: (...roles: Role[]) => boolean;
}

const initialState = {
  accessToken: null,
  tokenType: "bearer",
  user: null,
  isAuthenticated: false,
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      ...initialState,
      setSession: (response) => {
        set({
          accessToken: response.access_token,
          tokenType: response.token_type,
          user: response.user,
          isAuthenticated: true,
        });
      },
      logout: () => {
        sessionStorage.removeItem("industrial-rag-chat-v1");
        set(initialState);
      },
      hasRole: (...roles) => {
        const role = get().user?.role;
        return Boolean(role && roles.includes(role));
      },
    }),
    {
      name: "industrial-rag-auth-v1",
      storage: createJSONStorage(() => sessionStorage),
      partialize: ({ accessToken, tokenType, user, isAuthenticated }) => ({
        accessToken,
        tokenType,
        user,
        isAuthenticated,
      }),
    },
  ),
);
