import { apiClient } from "./client";
import type {
  CreateUserRequest,
  CreateUserResponse,
  LoginRequest,
  LoginResponse,
  UserInfo,
} from "./types";

export const authApi = {
  async login(payload: LoginRequest): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>("/auth/login", payload);
    return response.data;
  },

  async listUsers(): Promise<UserInfo[]> {
    const response = await apiClient.get<UserInfo[]>("/auth/users");
    return response.data;
  },

  async createUser(payload: CreateUserRequest): Promise<CreateUserResponse> {
    const response = await apiClient.post<CreateUserResponse>("/auth/users", payload);
    return response.data;
  },
};
