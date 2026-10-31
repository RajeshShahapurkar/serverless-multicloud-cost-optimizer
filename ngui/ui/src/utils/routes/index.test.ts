import { routes } from "./index";

describe("MVP route registry", () => {
  const registeredPages = routes.map(({ page }) => page);

  it("keeps authentication and account onboarding routes", () => {
    expect(registeredPages).toEqual(
      expect.arrayContaining([
        "Login",
        "Register",
        "PasswordRecovery",
        "EmailVerification",
        "CloudAccountsOverview",
        "CloudAccountDetails",
        "ConnectCloudAccount",
      ])
    );
  });

  it("keeps the multi-cloud cost optimization journeys", () => {
    expect(registeredPages).toEqual(
      expect.arrayContaining([
        "Dashboard",
        "Expenses",
        "CloudExpensesBreakdown",
        "PoolExpensesBreakdown",
        "OwnerExpensesBreakdown",
        "CloudCostComparison",
        "Resources",
        "Resource",
        "Recommendations",
      ])
    );
  });

  it("does not register unrelated feature routes", () => {
    expect(registeredPages).not.toEqual(
      expect.arrayContaining([
        "MlTasks",
        "MlModels",
        "BIExports",
        "ConnectJira",
        "ConnectSlack",
        "K8sRightsizing",
        "PowerSchedules",
        "Environments",
        "Anomalies",
      ])
    );
  });
});
