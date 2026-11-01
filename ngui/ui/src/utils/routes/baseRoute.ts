import { lazy } from "react";
import { v4 as uuidv4 } from "uuid";
import MainLayout from "layouts/MainLayout";

// Explicit imports prevent Vite from bundling pages excluded from the MVP.
const pageLoaders = {
  AcceptInvitation: () => import("../../pages/AcceptInvitation/index.ts"),
  OrganizationsOverview: () => import("../../pages/OrganizationsOverview/index.ts"),
  Invited: () => import("../../pages/Invited/index.ts"),
  Authorization: () => import("../../pages/Authorization/index.ts"),
  PasswordRecovery: () => import("../../pages/PasswordRecovery/index.ts"),
  EmailVerification: () => import("../../pages/EmailVerification/index.ts"),
  Initialize: () => import("../../pages/Initialize/index.ts"),
  Dashboard: () => import("../../pages/Dashboard/index.ts"),
  CloudAccountsOverview: () => import("../../pages/CloudAccountsOverview/index.ts"),
  CloudAccountDetails: () => import("../../pages/CloudAccountDetails/index.ts"),
  ConnectCloudAccount: () => import("../../pages/ConnectCloudAccount/index.ts"),
  Expenses: () => import("../../pages/Expenses/index.ts"),
  CloudExpensesBreakdown: () => import("../../pages/CloudExpensesBreakdown/index.ts"),
  PoolExpensesBreakdown: () => import("../../pages/PoolExpensesBreakdown/index.ts"),
  OwnerExpensesBreakdown: () => import("../../pages/OwnerExpensesBreakdown/index.ts"),
  CloudCostComparison: () => import("../../pages/CloudCostComparison/index.ts"),
  Resources: () => import("../../pages/Resources/index.ts"),
  Resource: () => import("../../pages/Resource/index.ts"),
  ClusterTypes: () => import("../../pages/ClusterTypes/index.ts"),
  CreateClusterType: () => import("../../pages/CreateClusterType/index.ts"),
  ResourcesPerspectives: () => import("../../pages/ResourcesPerspectives/index.ts"),
  Recommendations: () => import("../../pages/Recommendations/index.ts"),
  Settings: () => import("../../pages/Settings/index.ts"),
  OrganizationOptions: () => import("../../pages/OrganizationOptions/index.ts"),
  ThemeSettings: () => import("../../pages/ThemeSettings/index.ts"),
  Error: () => import("../../pages/Error/index.ts"),
};

class BaseRoute {
  key = uuidv4();

  link = "";

  page = "";

  layout = MainLayout;

  component = lazy(() => {
    const loader = pageLoaders[this.page as keyof typeof pageLoaders];
    if (!loader) {
      return Promise.reject(new Error(`Unknown MVP page: ${this.page}`));
    }
    return loader();
  });
}

export default BaseRoute;
