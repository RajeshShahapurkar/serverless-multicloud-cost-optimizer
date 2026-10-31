import acceptInvitationRoute from "./acceptInvitationRoute";
import BaseRoute from "./baseRoute";
import cloudCostComparisonRoute from "./cloudCostComparisonRoute";
import cloudExpensesRoute from "./cloudExpensesRoute";
import clusterTypesRoute from "./clusterTypesRoute";
import createClusterTypeRoute from "./createClusterTypeRoute";
import createDataSourceRoute from "./createDataSourceRoute";
import dataSourceOverviewRoute from "./dataSourceOverviewRoute";
import dataSourcesRoute from "./dataSourcesRoute";
import emailVerificationRoute from "./emailVerificationRoute";
import expensesRoute from "./expensesRoute";
import homeRoute from "./homeRoute";
import initializeRoute from "./initializeRoute";
import invitedRoute from "./invitedRoute";
import loginRoute from "./loginRoute";
import notFoundRoute from "./notFoundRoute";
import organizationOptionsRoute from "./organizationOptionsRoute";
import organizationsOverviewRoute from "./organizationsOverviewRoute";
import ownerExpensesRoute from "./ownerExpensesRoute";
import poolExpensesRoute from "./poolExpensesRoute";
import passwordRecoveryRoute from "./passwordRecoveryRoute";
import recommendationsRoute from "./recommendationsRoute";
import registerRoute from "./registerRoute";
import resourceRoute from "./resourceRoute";
import resourcesPerspectives from "./resourcesPerspectives";
import resourcesRoute from "./resourcesRoute";
import settingsRoute from "./settingsRoute";
import themeSettingsRoute from "./themeSettingsRoute";

export const routes = [
  // Authentication and first-run organization setup.
  acceptInvitationRoute,
  organizationsOverviewRoute,
  invitedRoute,
  loginRoute,
  registerRoute,
  passwordRecoveryRoute,
  emailVerificationRoute,
  initializeRoute,

  // MVP cost visibility and cloud-account management.
  homeRoute,
  dataSourcesRoute,
  dataSourceOverviewRoute,
  createDataSourceRoute,
  expensesRoute,
  cloudExpensesRoute,
  poolExpensesRoute,
  ownerExpensesRoute,
  cloudCostComparisonRoute,

  // Resource inventory and optimization.
  resourcesRoute,
  resourceRoute,
  clusterTypesRoute,
  createClusterTypeRoute,
  resourcesPerspectives,
  recommendationsRoute,

  // Basic account preferences.
  settingsRoute,
  organizationOptionsRoute,
  themeSettingsRoute,

  // Keep the fallback last for route matching.
  notFoundRoute,
];

export default BaseRoute;
