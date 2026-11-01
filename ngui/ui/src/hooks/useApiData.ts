import { createSelector } from "reselect";
import { RESTAPI, AUTH } from "api";
import { useShallowEqualSelector } from "hooks/useShallowEqualSelector";

const restApiSelector = (state) => state[RESTAPI];
const authSelector = (state) => state[AUTH];

const apiSelector = createSelector(
  restApiSelector,
  authSelector,
  (_, props) => props,
  (...args) => {
    const [restapi, auth, { label, defaultValue }] = args;
    return { ...restapi, ...auth }[label] || defaultValue;
  }
);

export const useApiData = (label, defaultValue = {}) => ({
  apiData: useShallowEqualSelector((state) => apiSelector(state, { label, defaultValue })),
});
