import MainMenuSectionTitle from "components/MainMenuSectionTitle";
import { MAIN_MENU_SECTION_IDS } from "components/MenuGroupWrapper/reducer";
import { OPTSCALE_CAPABILITY } from "utils/constants";
import cloudCostComparisonMenuItem from "./cloudCostComparisonMenuItem";
import dataSources from "./dataSourcesMenuItem";
import expenses from "./expensesMenuItem";
import home from "./homeMenuItem";
import recommendations from "./recommendationsMenuItem";
import resources from "./resourcesMenuItem";
import settings from "./settingsMenuItem";

export default [
  {
    id: MAIN_MENU_SECTION_IDS.HOME,
    items: [home, recommendations, resources],
  },
  {
    id: MAIN_MENU_SECTION_IDS.FINOPS,
    menuSectionTitle: <MainMenuSectionTitle messageId="finops" />,
    items: [expenses, cloudCostComparisonMenuItem],
    capability: OPTSCALE_CAPABILITY.FINOPS,
  },
  {
    id: MAIN_MENU_SECTION_IDS.SYSTEM,
    menuSectionTitle: <MainMenuSectionTitle messageId="system" />,
    items: [dataSources, settings],
  },
];
