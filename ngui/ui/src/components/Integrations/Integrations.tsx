import Grid from "@mui/material/Grid";
import ActionBar from "components/ActionBar";
import PageContentWrapper from "components/PageContentWrapper";
import IntegrationsBIExportContainer from "containers/IntegrationsBIExportContainer";
import IntegrationsGoogleCalendarContainer from "containers/IntegrationsGoogleCalendarContainer";
import { getSquareNodesStyle } from "utils/layouts";
import { BI_EXPORT } from "./BIExport";
import GitHub from "./GitHub";
import { GITHUB } from "./GitHub/GitHub";
import GitLab from "./GitLab";
import { GITLAB } from "./GitLab/GitLab";
import { GOOGLE_CALENDAR } from "./GoogleCalendar/GoogleCalendar";
import Jenkins from "./Jenkins";
import { JENKINS } from "./Jenkins/Jenkins";

const actionBarDefinition = {
  title: {
    messageId: "integrations",
  },
};

const integrationsGridItems = [
  {
    node: <IntegrationsGoogleCalendarContainer />,
    key: GOOGLE_CALENDAR,
  },
  {
    node: <IntegrationsBIExportContainer />,
    key: BI_EXPORT,
  },
  {
    node: <GitLab />,
    key: GITLAB,
  },
  {
    node: <GitHub />,
    key: GITHUB,
  },
  {
    node: <Jenkins />,
    key: JENKINS,
  },
];

const Integrations = () => (
  <>
    <ActionBar data={actionBarDefinition} />
    <PageContentWrapper>
      <Grid container>
        {integrationsGridItems.map(({ key, node }, i) => (
          <Grid key={key} item md={12} lg={6} sx={getSquareNodesStyle(integrationsGridItems.length, i)}>
            {node}
          </Grid>
        ))}
      </Grid>
    </PageContentWrapper>
  </>
);

export default Integrations;
