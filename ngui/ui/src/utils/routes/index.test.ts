import { routes } from "./index";

describe("MVP route registry", () => {
  const registeredPages = routes.map(({ page }) => page);

  it("keeps authentication and account onboarding routes", () => {
    expect(registeredPages).toEqual(
      expect.arrayContaining([
        "Authorization",
        "AcceptInvitation",
        "OrganizationsOverview",
        "Invited",
        "PasswordRecovery",
        "EmailVerification",
        "Initialize",
        "CloudAccountsOverview",
        "CloudAccountDetails",
        "ConnectCloudAccount",
      ])
    );
    expect(registeredPages.filter((page) => page === "Authorization")).toHaveLength(2);
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
        "ClusterTypes",
        "CreateClusterType",
        "ResourcesPerspectives",
        "Recommendations",
        "Settings",
        "OrganizationOptions",
        "ThemeSettings",
        "Error",
      ])
    );
  });

  it("does not register unrelated feature routes", () => {
    for (const excluded of [
      "MlTasks",
      "MlModels",
      "BIExports",
      "ConnectJira",
      "ConnectSlack",
      "K8sRightsizing",
      "PowerSchedules",
      "Environments",
      "Anomalies",
    ]) {
      expect(registeredPages).not.toContain(excluded);
    }
  });
});
