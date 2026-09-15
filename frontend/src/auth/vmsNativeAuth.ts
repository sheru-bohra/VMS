let vmsNativeAccessToken: string | null = null;

export function setVmsNativeAccessToken(token: string | null): void {
  vmsNativeAccessToken = token;
}

export function getVmsNativeAccessToken(): string | null {
  return vmsNativeAccessToken;
}

export function clearVmsNativeAccessToken(): void {
  vmsNativeAccessToken = null;
}
